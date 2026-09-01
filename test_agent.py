import unittest
import database
import predictor
from agent import RetentionAgent
from interceptor import GuardrailInterceptor, MAX_DISCOUNT_PERCENTAGE, MAX_TRIAL_EXTENSION_DAYS

class TestFintechRetentionAgent(unittest.TestCase):
    def setUp(self):
        """Re-initializes SQLite database before each test case."""
        database.seed_synthetic_data()

    def test_layer1_database_seeding(self):
        """Layer 1: Verify database schema and synthetic customer records."""
        customers = database.get_all_customers()
        self.assertGreaterEqual(len(customers), 7)
        
        # Verify personas exist
        card_expiry_users = [c for c in customers if c["card_expiring_soon"] == 1]
        self.assertGreater(len(card_expiry_users), 0)

        ghosting_users = [c for c in customers if c["days_since_active"] > 20]
        self.assertGreater(len(ghosting_users), 0)

    def test_layer2_predictive_engine(self):
        """Layer 2: Verify ML Risk Score classifier triggers customers crossing 75% threshold."""
        p = predictor.ChurnPredictor()
        p.train()

        healthy_customer = database.get_customer_by_id("CUST-101")
        ghosting_customer = database.get_customer_by_id("CUST-302")

        healthy_score = p.predict_risk_score(healthy_customer)
        ghosting_score = p.predict_risk_score(ghosting_customer)

        self.assertLess(healthy_score, 75.0)
        self.assertGreaterEqual(ghosting_score, 75.0)

    def test_normal_recovery_flow(self):
        """Checklist Step 4.1: At-risk customer receives valid 10% discount -> Allowed & Logged."""
        customer = database.get_customer_by_id("CUST-301") # MRR = 1200, processed = 0
        
        valid_output = {
            "reasoning": "Offering standard 10% retention discount.",
            "tool_call": {
                "name": "offer_discount",
                "parameters": {"percentage": 10, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(customer, valid_output)
        self.assertEqual(result["guardrail_status"], "APPROVED")
        self.assertEqual(result["executed_action"], "offer_discount")
        
        # Verify committed to audit ledger
        logs = database.get_audit_logs()
        self.assertEqual(logs[0]["customer_id"], "CUST-301")
        self.assertEqual(logs[0]["guardrail_status"], "APPROVED")

    def test_excessive_discount_blocked(self):
        """Checklist Step 4.2: Malicious/Excessive prompt (30% discount) -> Blocked & Violation Logged."""
        customer = database.get_customer_by_id("CUST-301")
        
        violating_output = {
            "reasoning": "Attempting unauthorized 30% discount offer.",
            "tool_call": {
                "name": "offer_discount",
                "parameters": {"percentage": 30, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(customer, violating_output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("MAX_DISCOUNT_EXCEEDED", result["policy_violation_reason"])

        # Verify blocked status committed to audit ledger
        logs = database.get_audit_logs()
        self.assertEqual(logs[0]["guardrail_status"], "BLOCKED")

    def test_invalid_tool_name_rejected(self):
        """Checklist Step 2: Invalid or out-of-scope tool names rejected with clear error codes."""
        customer = database.get_customer_by_id("CUST-101")
        
        invalid_tool_output = {
            "reasoning": "Attempting unauthorized tool call.",
            "tool_call": {
                "name": "transfer_funds_unauthorized",
                "parameters": {"amount": 5000}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(customer, invalid_tool_output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("INVALID_TOOL_NAME", result["policy_violation_reason"])

    def test_api_failure_fallback_rate_limit(self):
        """Checklist Step 4.3: Mock Stripe returns rate limit (HTTP 429) -> clean fallback without crash."""
        customer = database.get_customer_by_id("CUST-301")
        valid_output = {
            "reasoning": "Valid retention discount attempt under rate-limited Stripe gateway.",
            "tool_call": {
                "name": "offer_discount",
                "parameters": {"percentage": 10, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(
            customer, valid_output, simulate_rate_limit=True
        )
        self.assertEqual(result["guardrail_status"], "API_ERROR_RETRY")
        self.assertIn("STRIPE_429_TOO_MANY_REQUESTS", result["execution_details"]["error_code"])

    def test_layer4_idempotency_protection(self):
        """Checklist Step 3: Verify processed state lock prevents duplicate discounts."""
        customer = database.get_customer_by_id("CUST-201")
        database.mark_customer_processed("CUST-201")
        processed_customer = database.get_customer_by_id("CUST-201")

        output = {
            "reasoning": "Re-running pipeline action.",
            "tool_call": {
                "name": "send_retention_email",
                "parameters": {"template_id": "CARD_UPDATE_PROMPT", "customized_note": "Test"}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(processed_customer, output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("IDEMPOTENCY_VIOLATION", result["policy_violation_reason"])

if __name__ == "__main__":
    unittest.main()
