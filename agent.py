import os
import json

SYSTEM_PROMPT = """You are 'Razorpay Retention Sentinel', an autonomous fintech churn recovery AI agent integrated into Razorpay Subscriptions.
Your mission is to maximize ARR/GMV retention for merchants while MINIMIZING financial discount leakage.

Available Razorpay Dunning & Recovery Tools:
1. `razorpay_smart_retry(gateway_priority)`: Trigger Razorpay Optimus smart retry engine for failed recurring mandate payments. Use FIRST for involuntary payment failures!
2. `create_razorpay_payment_link(amount_inr, expires_in_hours)`: Generate instant Razorpay recovery payment link (via WhatsApp/SMS). Use when mandate fails or card is expiring.
3. `send_whatsapp_payment_reminder(template_id)`: Send automated WhatsApp payment dunning reminder.
4. `apply_razorpay_coupon(discount_percentage, duration_months)`: Offer temporary subscription coupon (e.g. 10%, 15%, max 15%). Use ONLY for voluntary churn / disengaged merchants!
5. `pause_subscription(duration_months)`: Temporarily pause subscription mandate for enterprise merchants during internal reviews.

HARD CONSTRAINTS:
- For INVOLUNTARY CHURN (Mandate failure / Expiring Card): Prioritize `razorpay_smart_retry` or `create_razorpay_payment_link`. Do NOT issue discounts for simple payment failures!
- For VOLUNTARY CHURN (Inactivity > 20 days): Consider modest coupon (max 15%) or subscription pause.
- Minimize discount percentage! Never propose excessive discounts when payment retry or payment link suffices.

OUTPUT MANDATE:
Respond with a single JSON object with NO markdown formatting:
{
  "reasoning": "Step-by-step breakdown of why this strategy was chosen based on merchant metrics",
  "tool_call": {
    "name": "<action_name>",
    "parameters": { ... }
  }
}
"""

class RetentionAgent:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", None)

    def generate_strategy(self, customer):
        """
        Determines optimal Razorpay dunning tool call for an at-risk merchant.
        Uses Gemini API if key is set; otherwise uses intelligent fallback logic.
        """
        if self.api_key:
            try:
                return self._call_gemini_api(customer)
            except Exception as e:
                print(f"[Agent Warning] Gemini API call failed ({e}). Using rule-augmented fallback.")
                return self._fallback_reasoning_engine(customer)
        else:
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
        if mandate_status == "FAILED_RETRY" or failed_payments >= 2:
            reasoning = (
                f"Merchant {c_id} has high risk score due to involuntary payment failure ({failed_payments} failed attempts, "
                f"mandate status: '{mandate_status}'). Action: Trigger Razorpay Optimus Smart Retry engine to recover payment across backup UPI/Cards."
            )
            tool_call = {
                "name": "razorpay_smart_retry",
                "parameters": {
                    "gateway_priority": "OPTIMUS_HIGH"
                }
            }
        elif card_expiring == 1 or mandate_status == "EXPIRING_SOON":
            reasoning = (
                f"Merchant {c_id} has an expiring payment mandate/card (<7 days). "
                f"Action: Generate instant Razorpay Payment Recovery Link (₹{customer['mrr']}) and send via WhatsApp reminder."
            )
            tool_call = {
                "name": "create_razorpay_payment_link",
                "parameters": {
                    "amount_inr": customer["mrr"],
                    "expires_in_hours": 24
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
        "name": "FinTech Global Solutions",
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
    print("\n[Razorpay Agent Output]:")
    print(json.dumps(result, indent=2))
