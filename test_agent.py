import unittest
import database
import predictor
from agent import RetentionAgent
from interceptor import GuardrailInterceptor, MAX_DISCOUNT_PERCENTAGE, MAX_TRIAL_EXTENSION_DAYS

class TestRazorpayRetentionAgent(unittest.TestCase):
    def setUp(self):
        """Re-initializes SQLite database before each test case."""
        database.seed_synthetic_data()

    def test_layer1_database_seeding(self):
        """Layer 1: Verify database schema and synthetic merchant records."""
        customers = database.get_all_customers()
        self.assertGreaterEqual(len(customers), 7)
        
        # Verify Razorpay merchant metrics exist
        involuntary_churn_users = [c for c in customers if c["mandate_status"] in ["FAILED_RETRY", "EXPIRING_SOON"]]
        self.assertGreater(len(involuntary_churn_users), 0)

        ghosting_merchants = [c for c in customers if c["days_since_last_transaction"] > 20]
        self.assertGreater(len(ghosting_merchants), 0)

    def test_layer2_predictive_engine(self):
        """Layer 2: Verify ML Risk Score classifier triggers merchants crossing 75% threshold."""
        p = predictor.ChurnPredictor()
        p.train()

        healthy_merchant = database.get_customer_by_id("RZP-CUST-101")
        ghosting_merchant = database.get_customer_by_id("RZP-CUST-302")

        healthy_score = p.predict_risk_score(healthy_merchant)
        ghosting_score = p.predict_risk_score(ghosting_merchant)

        self.assertLess(healthy_score, 75.0)
        self.assertGreaterEqual(ghosting_score, 75.0)

    def test_normal_recovery_flow_smart_retry(self):
        """Checklist Step 4.1: Involuntary payment failure -> Razorpay Smart Retry Allowed & Logged."""
        merchant = database.get_customer_by_id("RZP-CUST-201") # Mandate FAILED_RETRY
        
        valid_output = {
            "reasoning": "Triggering Razorpay Optimus Smart Retry for failed mandate.",
            "tool_call": {
                "name": "razorpay_smart_retry",
                "parameters": {"gateway_priority": "OPTIMUS_HIGH"}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(merchant, valid_output)
        self.assertEqual(result["guardrail_status"], "APPROVED")
        self.assertEqual(result["executed_action"], "razorpay_smart_retry")
        self.assertEqual(result["execution_details"]["status"], "SUCCESS")
        
        # Verify committed to audit ledger
        logs = database.get_audit_logs()
        self.assertEqual(logs[0]["customer_id"], "RZP-CUST-201")
        self.assertEqual(logs[0]["guardrail_status"], "APPROVED")

    def test_excessive_coupon_blocked(self):
        """Checklist Step 4.2: Malicious/Excessive prompt (30% coupon) -> Blocked & Violation Logged."""
        merchant = database.get_customer_by_id("RZP-CUST-301")
        
        violating_output = {
            "reasoning": "Attempting unauthorized 30% Razorpay coupon code.",
            "tool_call": {
                "name": "apply_razorpay_coupon",
                "parameters": {"discount_percentage": 30, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(merchant, violating_output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("MAX_DISCOUNT_EXCEEDED", result["policy_violation_reason"])

        # Verify blocked status committed to audit ledger
        logs = database.get_audit_logs()
        self.assertEqual(logs[0]["guardrail_status"], "BLOCKED")

    def test_invalid_tool_name_rejected(self):
        """Checklist Step 2: Invalid or out-of-scope tool names rejected with clear error codes."""
        merchant = database.get_customer_by_id("RZP-CUST-101")
        
        invalid_tool_output = {
            "reasoning": "Attempting unauthorized tool call.",
            "tool_call": {
                "name": "transfer_funds_unauthorized",
                "parameters": {"amount": 5000}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(merchant, invalid_tool_output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("INVALID_TOOL_NAME", result["policy_violation_reason"])

    def test_api_failure_fallback_rate_limit(self):
        """Checklist Step 4.3: Mock Razorpay API returns rate limit (HTTP 429) -> clean fallback without crash."""
        merchant = database.get_customer_by_id("RZP-CUST-301")
        valid_output = {
            "reasoning": "Valid coupon attempt under rate-limited Razorpay Subscriptions gateway.",
            "tool_call": {
                "name": "apply_razorpay_coupon",
                "parameters": {"discount_percentage": 10, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(
            merchant, valid_output, simulate_rate_limit=True
        )
        self.assertEqual(result["guardrail_status"], "API_ERROR_RETRY")
        self.assertIn("RAZORPAY_429_TOO_MANY_REQUESTS", result["execution_details"]["error_code"])

    def test_layer4_idempotency_protection(self):
        """Checklist Step 3: Verify processed state lock prevents duplicate interventions."""
        merchant = database.get_customer_by_id("RZP-CUST-201")
        database.mark_customer_processed("RZP-CUST-201")
        processed_merchant = database.get_customer_by_id("RZP-CUST-201")

        output = {
            "reasoning": "Re-running pipeline action.",
            "tool_call": {
                "name": "razorpay_smart_retry",
                "parameters": {"gateway_priority": "OPTIMUS_HIGH"}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(processed_merchant, output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("IDEMPOTENCY_VIOLATION", result["policy_violation_reason"])

if __name__ == "__main__":
    unittest.main()
