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

    def test_layer3_reasoning_engine(self):
        """Layer 3: Verify LLM agent generates structured JSON tool call outputs."""
        agent = RetentionAgent()
        sample_customer = database.get_customer_by_id("CUST-201")
        sample_customer["risk_score"] = 88.5

        output = agent.generate_strategy(sample_customer)
        self.assertIn("reasoning", output)
        self.assertIn("tool_call", output)
        self.assertIn("name", output["tool_call"])
        self.assertIn("parameters", output["tool_call"])

    def test_layer4_guardrail_discount_cap(self):
        """Layer 4: Interceptor MUST BLOCK discounts exceeding the 20% cap."""
        customer = database.get_customer_by_id("CUST-301") # MRR = 1200, processed = 0
        
        violating_output = {
            "reasoning": "Attempting 35% discount offer.",
            "tool_call": {
                "name": "offer_discount",
                "parameters": {"percentage": 35, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(customer, violating_output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("MAX_DISCOUNT_EXCEEDED", result["policy_violation_reason"])

    def test_layer4_guardrail_double_discount_block(self):
        """Layer 4: Interceptor MUST BLOCK discount stacking on customer with active discount."""
        customer = database.get_customer_by_id("CUST-303") # has_discount = 1

        output = {
            "reasoning": "Attempting discount on user with existing discount.",
            "tool_call": {
                "name": "offer_discount",
                "parameters": {"percentage": 10, "duration_months": 3}
            }
        }

        result = GuardrailInterceptor.evaluate_and_execute(customer, output)
        self.assertEqual(result["guardrail_status"], "BLOCKED")
        self.assertIn("DOUBLE_DISCOUNT_PROHIBITED", result["policy_violation_reason"])

    def test_layer4_idempotency_protection(self):
        """Layer 4: Interceptor MUST BLOCK duplicate actions on processed customers."""
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

    def test_explainability_audit_ledger(self):
        """Evaluation Checklist: Verify every decision is committed to Audit_Log table."""
        customer = database.get_customer_by_id("CUST-102")
        output = {
            "reasoning": "Test audit log entry.",
            "tool_call": {
                "name": "extend_trial",
                "parameters": {"days": 7}
            }
        }
        GuardrailInterceptor.evaluate_and_execute(customer, output)
        
        logs = database.get_audit_logs()
        self.assertGreater(len(logs), 0)
        latest = logs[0]
        self.assertEqual(latest["customer_id"], "CUST-102")
        self.assertEqual(latest["guardrail_status"], "APPROVED")

if __name__ == "__main__":
    unittest.main()
