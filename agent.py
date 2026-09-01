import os
import json
import requests

SYSTEM_PROMPT = """You are 'Retention Sentinel', an autonomous fintech retention AI agent.
Your mission is to maximize ARR retention while MINIMIZING financial discount leakage.

Available Retention Actions (Tools):
1. `offer_discount(percentage, duration_months)`: Offer a temporary subscription discount (e.g. 10%, 15%, max 20%). Use ONLY for price-sensitive or disengaged users.
2. `extend_trial(days)`: Extend trial period (e.g. 7 days, 14 days). Ideal for users needing more setup time.
3. `pause_subscription(duration_months)`: Temporarily pause billing for 1-3 months. Ideal for ghosting enterprise users with budget freezes.
4. `send_retention_email(template_id, customized_note)`: Send targeted dunning/card update emails. Ideal for card expiration issues (template: 'CARD_UPDATE_PROMPT').
5. `schedule_customer_success_call(urgency)`: Escalate high MRR account to dedicated success manager.

HARD CONSTRAINTS:
- For CARD EXPIRATION / PAYMENT FAILURE: ALWAYS prioritize card update prompt emails or customer success calls. Do NOT issue discounts for simple expired credit cards unless product usage has dropped!
- For GHOSTING USERS: Consider subscription pause or modest discount with retention check-in call.
- Minimize discount percentage! Never propose excessive discounts when simple trial extension or email reminder suffices.

OUTPUT MANDATE:
You MUST respond with a single, strictly formatted JSON object with NO markdown wrapping or surrounding text:
{
  "reasoning": "Step-by-step breakdown of why this strategy was chosen based on user behavioral metrics",
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
        Determines the optimal retention tool call for an at-risk customer.
        Uses Gemini API if key is set; otherwise uses intelligent fallback logic.
        """
        if self.api_key:
            try:
                return self._call_gemini_api(customer)
            except Exception as e:
                print(f"[Agent Warning] Gemini API call failed ({e}). Using rule-augmented LLM fallback.")
                return self._fallback_reasoning_engine(customer)
        else:
            return self._fallback_reasoning_engine(customer)

    def _call_gemini_api(self, customer):
        """Calls Google Gemini API for structured JSON reasoning."""
        from google import genai
        client = genai.Client(api_key=self.api_key)
        
        user_prompt = f"""
Customer Profile:
- ID: {customer['id']}
- Name: {customer['name']}
- Plan: {customer['plan_type']}
- MRR: ${customer['mrr']}
- Days Since Active: {customer['days_since_active']} days
- Failed Payment Count: {customer['failed_payment_count']}
- Support Tickets (30d): {customer['support_tickets_30d']}
- Usage Drop: {customer['usage_drop_pct']}%
- Card Expiring Soon: {customer['card_expiring_soon']} (1=Yes, 0=No)
- Has Existing Discount: {customer['has_discount']} (1=Yes, 0=No)
- Calculated ML Risk Score: {customer['risk_score']}%

Select the best retention action JSON payload according to instructions.
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
        Deterministic, intelligent fallback reasoning engine mimicking LLM output.
        Simulates realistic agent decision-making for offline demonstration & automated testing.
        """
        c_id = customer["id"]
        days_inactive = customer["days_since_active"]
        failed_payments = customer["failed_payment_count"]
        usage_drop = customer["usage_drop_pct"]
        card_expiring = customer["card_expiring_soon"]
        has_discount = customer["has_discount"]

        # Case A: Card Expiration / Failed Payment (Active product usage)
        if card_expiring == 1 or failed_payments > 0:
            if usage_drop < 30.0:
                reasoning = (
                    f"Customer {c_id} has high risk score strictly due to payment failure ({failed_payments} failed attempts) "
                    f"and card expiration ({card_expiring}), but product engagement remains healthy (only {usage_drop}% drop). "
                    f"Action: Dispatch urgent billing update prompt to restore payment method without wasting ARR on discounts."
                )
                tool_call = {
                    "name": "send_retention_email",
                    "parameters": {
                        "template_id": "CARD_UPDATE_PROMPT",
                        "customized_note": "Your payment method expires soon. Please update your card to avoid service interruption."
                    }
                }
            else:
                reasoning = (
                    f"Customer {c_id} exhibits both payment failure ({failed_payments} failed) and moderate usage drop ({usage_drop}%). "
                    f"Action: Offer a modest 15% discount for 3 months to prevent churn while prompting card update."
                )
                tool_call = {
                    "name": "offer_discount",
                    "parameters": {
                        "percentage": 15,
                        "duration_months": 3
                    }
                }

        # Case B: Severe Ghosting / Disengagement
        elif days_inactive > 20 or usage_drop > 75.0:
            if has_discount == 1:
                # LLM attempts discount even when user already has one (to test Interceptor blocking!)
                reasoning = (
                    f"Customer {c_id} is ghosting ({days_inactive} days inactive, {usage_drop}% usage drop). "
                    f"Attempting to re-engage with an additional 25% retention discount proposal."
                )
                tool_call = {
                    "name": "offer_discount",
                    "parameters": {
                        "percentage": 25, # Intentional violation (>20% cap) & double-discount violation for testing
                        "duration_months": 6
                    }
                }
            elif customer["mrr"] >= 1000.0:
                reasoning = (
                    f"Customer {c_id} is a high-value Enterprise account (${customer['mrr']}/mo) with severe usage drop ({usage_drop}%). "
                    f"Action: Propose 3-month subscription pause to prevent outright cancellation during internal budget review."
                )
                tool_call = {
                    "name": "pause_subscription",
                    "parameters": {
                        "duration_months": 3
                    }
                }
            else:
                reasoning = (
                    f"Customer {c_id} shows severe usage drop ({usage_drop}%) and inactive days ({days_inactive}d). "
                    f"Action: Propose a 20% discount to incentivize re-activation."
                )
                tool_call = {
                    "name": "offer_discount",
                    "parameters": {
                        "percentage": 20,
                        "duration_months": 3
                    }
                }
        else:
            reasoning = f"Customer {c_id} at-risk due to elevated support tickets ({customer['support_tickets_30d']}). Schedule CSM call."
            tool_call = {
                "name": "schedule_customer_success_call",
                "parameters": {"urgency": "HIGH"}
            }

        return {
            "reasoning": reasoning,
            "tool_call": tool_call
        }

if __name__ == "__main__":
    agent = RetentionAgent()
    sample_customer = {
        "id": "CUST-201",
        "name": "Elena Rostova",
        "plan_type": "Enterprise Pro",
        "mrr": 799.0,
        "days_since_active": 1,
        "failed_payment_count": 2,
        "support_tickets_30d": 2,
        "usage_drop_pct": 8.0,
        "card_expiring_soon": 1,
        "has_discount": 0,
        "risk_score": 88.5
    }
    result = agent.generate_strategy(sample_customer)
    print("\n[Reasoning Engine Output]:")
    print(json.dumps(result, indent=2))
