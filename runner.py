import json
import sys
import database
from predictor import run_predictive_pipeline
from config import Config
from agent import RetentionAgent
from interceptor import GuardrailInterceptor

# Ensure stdout handles UTF-8 on Windows command line
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_autonomous_pipeline(auto_remediate=False):
    print("\n=======================================================")
    print(" [AUTONOMOUS FINTECH CHURN RECOVERY AGENT PIPELINE] ")
    print("=======================================================\n")

    # Step 1: Layer 1 - Load/Verify Database
    customers = database.get_all_customers()
    print(f"--> Layer 1 [Storage & Ledger]: Loaded {len(customers)} merchant accounts from SQLite database.")

    # Step 2: Layer 2 - Run ML Churn Risk Predictor
    at_risk_customers = run_predictive_pipeline()

    # Step 3 & 4: Layer 3 (Reasoning Engine) & Layer 4 (Interceptor)
    print("\n=======================================================")
    print("   LAYERS 3 & 4: REASONING ENGINE & SAFETY INTERCEPTOR ")
    print("=======================================================")

    agent = RetentionAgent()
    results_summary = {
        "processed_count": len(at_risk_customers),
        "approved_actions": 0,
        "blocked_actions": 0,
        "remediated_actions": 0
    }

    for idx, customer in enumerate(at_risk_customers, 1):
        print(f"\n-------------------------------------------------------")
        print(f"[{idx}/{len(at_risk_customers)}] Processing Merchant: {customer['id']} - {customer['name']}")
        print(f"    Category: {customer['merchant_category']} | MRR/GMV=₹{customer['mrr']} | Last Transaction={customer['days_since_last_transaction']}d ago")
        print(f"    Failure Rate={customer['payment_failure_rate']*100:.1f}% | Failed Mandates={customer['failed_payment_count']} | Status={customer['mandate_status']}")
        print(f"    ML Risk Score: {customer['risk_score']}% (Triggered > {Config.RISK_TRIGGER_THRESHOLD}%)")

        # Check Idempotency before calling LLM
        if customer.get("processed") == 1:
            print("    [IDEMPOTENCY ALERT]: Merchant already processed in prior run.")

        # Layer 3: Reasoning Engine
        print("    [Reasoning Engine] Generating recovery strategy...")
        llm_output = agent.generate_strategy(customer)
        print(f"    [LLM Reasoning]: \"{llm_output.get('reasoning')}\"")
        print(f"    [LLM Proposed Action]: {json.dumps(llm_output.get('tool_call'))}")

        # Layer 4: Interceptor Check
        print("    [Guardrail Interceptor] Validating proposed action against company financial policies...")
        interceptor_result = GuardrailInterceptor.evaluate_and_execute(
            customer=customer,
            llm_output=llm_output,
            auto_remediate_violators=auto_remediate
        )

        status = interceptor_result["guardrail_status"]
        if status == "APPROVED":
            results_summary["approved_actions"] += 1
            print(f"    [VERDICT]: APPROVED")
            print(f"    [API Execution]: {interceptor_result['execution_details']}")
        elif status == "AUTO_REMEDIATED":
            results_summary["remediated_actions"] += 1
            print(f"    [VERDICT]: AUTO-REMEDIATED (Capping policy violation)")
            print(f"    [Policy Reason]: {interceptor_result['policy_violation_reason']}")
            print(f"    [API Execution]: {interceptor_result['execution_details']}")
        else:
            results_summary["blocked_actions"] += 1
            print(f"    [VERDICT]: BLOCKED (Hard Financial Barrier Triggered)")
            print(f"    [Policy Violation]: {interceptor_result['policy_violation_reason']}")

    # Step 5: Final Summary & Audit Verification
    print("\n=======================================================")
    print("               PIPELINE EXECUTION SUMMARY              ")
    print("=======================================================")
    print(f" Total At-Risk Merchants Evaluated: {results_summary['processed_count']}")
    print(f" Actions Approved & Executed      : {results_summary['approved_actions']}")
    print(f" Actions Auto-Remediated          : {results_summary['remediated_actions']}")
    print(f" Actions Blocked (Guardrails)     : {results_summary['blocked_actions']}")
    
    logs = database.get_audit_logs()
    print(f" Total Ledger Entries Committed   : {len(logs)}")
    print("=======================================================\n")

def test_idempotency():
    print("\n=======================================================")
    print("      TESTING IDEMPOTENCY & RESTART PROTECTION        ")
    print("=======================================================")
    print("Re-running pipeline on merchant accounts who have ALREADY been processed...")
    run_autonomous_pipeline()

if __name__ == "__main__":
    database.seed_synthetic_data()
    run_autonomous_pipeline(auto_remediate=False)
    test_idempotency()
