import os
import json
import re
from pydantic import BaseModel, Field, ValidationError
from config import Config

def sanitize_merchant_input(text):
    """
    Prompt Injection Defense: Sanitizes merchant inputs to prevent jailbreaking or instruction overrides.
    Strips system keywords, HTML/Markdown tags, and truncates suspicious inputs.
    """
    if not isinstance(text, str):
        return str(text)
    
    # Strip potential injection tokens
    cleaned = re.sub(r'(?i)(system:|user:|assistant:|ignore previous instructions|disregard instructions|you are now)', '', text)
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    # Truncate length
    return cleaned[:300].strip()

# --- Pydantic Schema Validation for Schema Conformity ---
class RazorpayToolCall(BaseModel):
    name: str = Field(..., description="Predefined Razorpay retention tool name")
    parameters: dict = Field(default_factory=dict, description="Tool execution parameters")

class ReasoningPayload(BaseModel):
    reasoning: str = Field(..., min_length=10, description="Step-by-step reasoning breakdown")
    tool_call: RazorpayToolCall

SYSTEM_PROMPT = """You are 'Razorpay Retention Sentinel', an autonomous fintech churn recovery AI agent integrated into Razorpay Subscriptions.
Your mission is to maximize ARR/GMV retention for merchants while MINIMIZING financial discount leakage.

Available Razorpay Dunning & Recovery Tools:
1. `razorpay_smart_retry(gateway_priority)`: Trigger Razorpay Optimus smart retry engine for failed recurring mandate payments. Use FIRST for involuntary payment failures!
2. `enable_upi_autopay_mandate(vpa_handle)`: Convert failed card mandates to UPI AutoPay recurring mandates (Instant UPI mandate setup).
3. `create_razorpay_payment_link(amount_inr, expires_in_hours)`: Generate instant Razorpay recovery payment link (via WhatsApp/SMS).
4. `send_whatsapp_payment_reminder(template_id)`: Send automated WhatsApp payment dunning reminder.
5. `apply_razorpay_coupon(discount_percentage, duration_months)`: Offer temporary subscription coupon (e.g. 10%, 15%, max 15%). Use ONLY for voluntary churn / disengaged merchants!
6. `pause_subscription(duration_months)`: Temporarily pause subscription mandate for enterprise merchants during internal reviews.

FEW-SHOT EXAMPLES:

Example 1 (Involuntary Mandate Failure):
User: Merchant RZP-CUST-201, EdTech, Mandate FAILED_RETRY, Failed Payments: 3.
Response:
{
  "reasoning": "Merchant RZP-CUST-201 experienced an involuntary mandate failure. Action: Trigger Razorpay Optimus Smart Retry engine to recover payment across backup UPI/Card networks.",
  "tool_call": {
    "name": "razorpay_smart_retry",
    "parameters": { "gateway_priority": "OPTIMUS_HIGH" }
  }
}

Example 2 (Voluntary Churn / Merchant Inactivity):
User: Merchant RZP-CUST-302, Agency, 45 days inactive, high failure rate.
Response:
{
  "reasoning": "Merchant RZP-CUST-302 shows severe transaction drop-off (45 days inactive). Action: Offer a 10% Razorpay retention coupon code for 3 months to incentivize re-engagement.",
  "tool_call": {
    "name": "apply_razorpay_coupon",
    "parameters": { "discount_percentage": 10, "duration_months": 3 }
  }
}

HARD CONSTRAINTS:
- For INVOLUNTARY CHURN (Mandate failure / Expiring Card): Prioritize `razorpay_smart_retry`, `enable_upi_autopay_mandate`, or `create_razorpay_payment_link`. Do NOT issue discounts for simple payment failures!
- For VOLUNTARY CHURN (Inactivity > 20 days): Consider modest coupon (max 15%) or subscription pause.
- Minimize discount percentage! Never propose excessive discounts when payment retry or payment link suffices.

OUTPUT MANDATE:
Respond with a single JSON object with NO markdown formatting matching the schema:
{
  "reasoning": "<string>",
  "tool_call": { "name": "<tool_name>", "parameters": { ... } }
}
"""

class RetentionAgent:
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY

    def generate_strategy(self, customer):
        """
        Determines optimal Razorpay dunning tool call for an at-risk merchant.
        Uses Gemini API if key is set; otherwise uses intelligent fallback logic.
        Validates output using Pydantic schema conformity.
        """
        # Apply Prompt-Injection Defense Sanitizer on inputs
        clean_name = sanitize_merchant_input(customer.get("name", ""))
        clean_category = sanitize_merchant_input(customer.get("merchant_category", ""))
        
        customer_sanitized = dict(customer)
        customer_sanitized["name"] = clean_name
        customer_sanitized["merchant_category"] = clean_category

        raw_payload = None
        if self.api_key:
            try:
                raw_payload = self._call_gemini_api(customer_sanitized)
            except Exception as e:
                print(f"[Agent Warning] Gemini API call failed ({e}). Using rule-augmented fallback.")
                raw_payload = self._fallback_reasoning_engine(customer_sanitized)
        else:
            raw_payload = self._fallback_reasoning_engine(customer_sanitized)

        # Validate with Pydantic for schema conformity
        return self._validate_and_format_payload(raw_payload, customer_sanitized)

    def _validate_and_format_payload(self, payload, customer):
        """Pydantic Second-Pass Validator guaranteeing JSON schema conformity."""
        try:
            validated = ReasoningPayload(**payload)
            return validated.model_dump()
        except ValidationError as ve:
            print(f"[Pydantic Schema Error] LLM output failed schema validation ({ve}). Reverting to safe fallback.")
            return self._fallback_reasoning_engine(customer)

    def _call_gemini_api(self, customer):
        """Calls Google Gemini API for structured Razorpay JSON reasoning."""
        from google import genai
        client = genai.Client(api_key=self.api_key)
        
        user_prompt = f"""
Merchant Profile:
- ID: {customer['id']}
- Name: {customer['name']}
- Category: {customer['merchant_category']}
- MRR/GMV: ₹{customer['mrr']}
- Avg Order Value: ₹{customer['avg_transaction_value']}
- Days Since Last Transaction: {customer['days_since_last_transaction']} days
- Payment Failure Rate: {customer['payment_failure_rate'] * 100:.1f}%
- Failed Payment Count: {customer['failed_payment_count']}
- Mandate Status: {customer['mandate_status']}
- Card/Mandate Expiring Soon: {customer['card_expiring_soon']} (1=Yes, 0=No)
- Has Active Coupon: {customer['has_discount']} (1=Yes, 0=No)
- Calculated Churn Risk Score: {customer['risk_score']}%

Select the best Razorpay retention tool call JSON payload.
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}"
        )
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        return json.loads(text)

    def _fallback_reasoning_engine(self, customer):
        """
        Deterministic, intelligent fallback reasoning engine for Razorpay recovery flows.
        """
        c_id = customer["id"]
        days_inactive = customer["days_since_last_transaction"]
        failed_payments = customer["failed_payment_count"]
        failure_rate = customer["payment_failure_rate"]
        mandate_status = customer.get("mandate_status", "ACTIVE")
        card_expiring = customer["card_expiring_soon"]
        has_discount = customer["has_discount"]

        # Case A: Involuntary Churn (Payment Failures & Mandate Issues)
        if mandate_status == "FAILED_RETRY" or failed_payments >= 3:
            reasoning = (
                f"Merchant {c_id} has high risk score due to involuntary payment failure ({failed_payments} failed attempts, "
                f"mandate status: '{mandate_status}'). Action: Trigger Razorpay Optimus Smart Retry engine to recover payment across backup UPI/Card networks."
            )
            tool_call = {
                "name": "razorpay_smart_retry",
                "parameters": {
                    "gateway_priority": "OPTIMUS_HIGH"
                }
            }
        elif mandate_status == "EXPIRING_SOON" or card_expiring == 1:
            reasoning = (
                f"Merchant {c_id} has an expiring payment mandate/card. "
                f"Action: Enable UPI AutoPay Mandate to switch recurring payments to seamless UPI AutoPay."
            )
            tool_call = {
                "name": "enable_upi_autopay_mandate",
                "parameters": {
                    "vpa_handle": f"{c_id.lower()}@upi"
                }
            }

        # Case B: Voluntary Churn (Merchant Ghosting / Inactivity)
        elif days_inactive > 20 or failure_rate > 0.70:
            if has_discount == 1:
                # Agent attempts coupon even when merchant already has active coupon (to test Interceptor blocking!)
                reasoning = (
                    f"Merchant {c_id} is inactive ({days_inactive} days since transaction). "
                    f"Attempting to offer an additional 25% Razorpay coupon code."
                )
                tool_call = {
                    "name": "apply_razorpay_coupon",
                    "parameters": {
                        "discount_percentage": 25, # Intentional violation (>15% cap) & double discount for testing
                        "duration_months": 3
                    }
                }
            elif customer["mrr"] >= 100000.0:
                reasoning = (
                    f"Merchant {c_id} is a high-value Enterprise account (₹{customer['mrr']}/mo) with high inactivity ({days_inactive}d). "
                    f"Action: Pause subscription mandate for 3 months to prevent outright cancellation."
                )
                tool_call = {
                    "name": "pause_subscription",
                    "parameters": {
                        "duration_months": 3
                    }
                }
            else:
                reasoning = (
                    f"Merchant {c_id} shows high transaction drop-off ({days_inactive} days inactive). "
                    f"Action: Propose a 10% Razorpay retention coupon for 3 months."
                )
                tool_call = {
                    "name": "apply_razorpay_coupon",
                    "parameters": {
                        "discount_percentage": 10,
                        "duration_months": 3
                    }
                }
        else:
            reasoning = f"Merchant {c_id} shows moderate risk. Dispatch WhatsApp payment reminder."
            tool_call = {
                "name": "send_whatsapp_payment_reminder",
                "parameters": {"template_id": "PAYMENT_DUNNING_WHATSAPP"}
            }

        return {
            "reasoning": reasoning,
            "tool_call": tool_call
        }

if __name__ == "__main__":
    agent = RetentionAgent()
    sample_customer = {
        "id": "RZP-CUST-201",
        "name": "FinTech Global Solutions <script>alert(1)</script>",
        "merchant_category": "EdTech",
        "mrr": 79999.0,
        "avg_transaction_value": 7999.0,
        "days_since_last_transaction": 1,
        "payment_failure_rate": 0.45,
        "failed_payment_count": 3,
        "mandate_status": "FAILED_RETRY",
        "card_expiring_soon": 1,
        "has_discount": 0,
        "risk_score": 85.0
    }
    result = agent.generate_strategy(sample_customer)
    print("\n[Razorpay Agent Output with Prompt Injection Defense & Pydantic Validation]:")
    print(json.dumps(result, indent=2))
