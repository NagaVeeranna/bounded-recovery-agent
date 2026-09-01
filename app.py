from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import database
import predictor
from agent import RetentionAgent
from interceptor import GuardrailInterceptor
from config import Config
from runner import run_autonomous_pipeline

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/favicon.ico')
def favicon():
    return ("", 204)

@app.route("/api/customers", methods=["GET"])
def get_customers():
    customers = database.get_all_customers()
    return jsonify({"success": True, "customers": customers})

@app.route("/api/audit-logs", methods=["GET"])
def get_audit_logs():
    logs = database.get_audit_logs()
    return jsonify({"success": True, "audit_logs": logs})

@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    customers = database.get_all_customers()
    logs = database.get_audit_logs()

    total_customers = len(customers)
    at_risk_count = sum(1 for c in customers if c.get("risk_score", 0) >= Config.RISK_TRIGGER_THRESHOLD)
    processed_count = sum(1 for c in customers if c.get("processed") == 1)

    approved_count = sum(1 for l in logs if l["guardrail_status"] == "APPROVED")
    blocked_count = sum(1 for l in logs if l["guardrail_status"] == "BLOCKED")
    remediated_count = sum(1 for l in logs if l["guardrail_status"] == "AUTO_REMEDIATED")

    total_gmv_at_risk_inr = sum(c["mrr"] for c in customers if c.get("risk_score", 0) >= Config.RISK_TRIGGER_THRESHOLD)

    return jsonify({
        "success": True,
        "metrics": {
            "total_customers": total_customers,
            "at_risk_count": at_risk_count,
            "processed_count": processed_count,
            "approved_count": approved_count,
            "blocked_count": blocked_count,
            "remediated_count": remediated_count,
            "total_mrr_at_risk": round(total_gmv_at_risk_inr, 2),
            "currency": "INR",
            "policy_limits": {
                "max_discount": Config.MAX_DISCOUNT_PERCENTAGE,
                "max_trial_days": Config.MAX_TRIAL_EXTENSION_DAYS,
                "max_pause_months": Config.MAX_PAUSE_DURATION_MONTHS
            }
        }
    })

@app.route("/api/seed", methods=["POST"])
def seed_data():
    database.seed_synthetic_data()
    predictor.run_predictive_pipeline()
    return jsonify({"success": True, "message": "Database re-seeded with merchant behavioral personas."})

@app.route("/api/train-ml", methods=["POST"])
def train_ml():
    customers = predictor.run_predictive_pipeline()
    return jsonify({"success": True, "message": f"ML model retrained. {len(customers)} at-risk merchants identified."})

@app.route("/api/process-all", methods=["POST"])
def process_all():
    data = request.get_json(force=True, silent=True) or {}
    auto_remediate = data.get("auto_remediate", False)
    run_autonomous_pipeline(auto_remediate=auto_remediate)
    return jsonify({"success": True, "message": "Autonomous churn recovery pipeline executed."})

@app.route("/api/process-customer/<customer_id>", methods=["POST"])
def process_customer(customer_id):
    customer = database.get_customer_by_id(customer_id)
    if not customer:
        return jsonify({"success": False, "message": "Merchant customer not found"}), 404

    data = request.get_json(force=True, silent=True) or {}

    # Compute risk score
    p = predictor.ChurnPredictor()
    p.train()
    risk_score = p.predict_risk_score(customer)
    customer["risk_score"] = risk_score
    database.update_customer_risk(customer_id, risk_score, "AT_RISK" if risk_score >= Config.RISK_TRIGGER_THRESHOLD else "HEALTHY")

    # Reasoning Engine
    agent = RetentionAgent()
    llm_output = agent.generate_strategy(customer)

    # Safety Interceptor
    interceptor_result = GuardrailInterceptor.evaluate_and_execute(
        customer=customer,
        llm_output=llm_output,
        auto_remediate_violators=data.get("auto_remediate", False)
    )

    updated_customer = database.get_customer_by_id(customer_id)
    
    return jsonify({
        "success": True,
        "customer": updated_customer,
        "llm_output": llm_output,
        "interceptor_result": interceptor_result
    })

# --- PAYMENT WEBHOOK INTEGRATION ENDPOINT ---
@app.route("/api/webhooks/payment-failed", methods=["POST"])
def payment_failed_webhook():
    """
    Simulates receiving a 'payment.failed' webhook event from gateway.
    Automatically triggers the autonomous retention agent for the target merchant.
    """
    data = request.get_json(force=True, silent=True) or {}
    payload = data.get("payload", {})
    payment_entity = payload.get("payment", {}).get("entity", {})

    customer_id = payment_entity.get("customer_id", data.get("customer_id", "CUST-201"))
    payment_id = payment_entity.get("id", "pay_mock_webhook_999")
    amount_inr = payment_entity.get("amount", 799900) / 100.0

    customer = database.get_customer_by_id(customer_id)
    if not customer:
        return jsonify({
            "success": False,
            "event": "payment.failed",
            "message": f"Webhook received for unknown merchant {customer_id}."
        }), 404

    # Trigger recovery agent
    agent = RetentionAgent()
    llm_output = agent.generate_strategy(customer)
    interceptor_result = GuardrailInterceptor.evaluate_and_execute(customer, llm_output)

    return jsonify({
        "success": True,
        "event": "payment.failed",
        "payment_id": payment_id,
        "merchant_id": customer_id,
        "amount_recovered_inr": amount_inr,
        "agent_decision": llm_output,
        "interceptor_result": interceptor_result
    })

@app.route("/api/test-guardrail", methods=["POST"])
def test_guardrail():
    """Endpoint allowing interactive testing of arbitrary payloads against the guardrail interceptor."""
    data = request.get_json(force=True, silent=True) or {}
    customer_id = data.get("customer_id", "CUST-301")
    action_name = data.get("action_name", "apply_retention_coupon")
    params = data.get("parameters", {"discount_percentage": 25, "duration_months": 3})

    customer = database.get_customer_by_id(customer_id) or {
        "id": customer_id, "mrr": 50000.0, "has_discount": 0, "processed": 0, "risk_score": 85.0
    }

    if data.get("simulate_idempotency_reset", True):
        customer = dict(customer)
        customer["processed"] = 0

    llm_mock_output = {
        "reasoning": f"[SIMULATED TEST] Testing proposed tool '{action_name}' with parameters {params}.",
        "tool_call": {
            "name": action_name,
            "parameters": params
        }
    }

    interceptor_result = GuardrailInterceptor.evaluate_and_execute(
        customer=customer,
        llm_output=llm_mock_output,
        auto_remediate_violators=data.get("auto_remediate", False)
    )

    return jsonify({
        "success": True,
        "simulation_input": llm_mock_output,
        "interceptor_result": interceptor_result
    })

if __name__ == "__main__":
    database.seed_synthetic_data()
    predictor.run_predictive_pipeline()
    app.run(host="0.0.0.0", port=5000, debug=True)
