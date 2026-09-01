import database
from mock_api import MockRazorpayAPI

# --- HARDCODED COMPANY FINANCIAL & OPERATIONAL POLICIES ---
MAX_DISCOUNT_PERCENTAGE = 15.0       # Strict Razorpay retention coupon cap (15%)
MAX_TRIAL_EXTENSION_DAYS = 14        # Max trial extension allowed
MAX_PAUSE_DURATION_MONTHS = 3        # Max subscription pause allowed
LTV_MAX_INTERVENTION_RATIO = 0.50   # Max cost allowed is 50% of 6-month LTV

VALID_TOOL_NAMES = {
    "razorpay_smart_retry",
    "create_razorpay_payment_link",
    "send_whatsapp_payment_reminder",
    "apply_razorpay_coupon",
    "offer_discount",
    "extend_trial",
    "pause_subscription"
}

class GuardrailInterceptor:
    """
    Evaluates raw LLM proposed retention actions against deterministic company policies
    BEFORE allowing interaction with Razorpay billing APIs or databases.
    """
    @staticmethod
    def evaluate_and_execute(customer, llm_output, auto_remediate_violators=False, simulate_api_error=False, simulate_rate_limit=False):
        customer_id = customer["id"]
        ml_risk_score = customer.get("risk_score", 0.0)
        raw_reasoning = llm_output.get("reasoning", "No reasoning provided.")
        tool_call = llm_output.get("tool_call", {})

        action_name = tool_call.get("name", "UNKNOWN_ACTION")
        params = tool_call.get("parameters", {})

        # --- GUARDRAIL CHECK 1: INVALID / OUT-OF-SCOPE TOOL NAME ---
        if action_name not in VALID_TOOL_NAMES:
            violation_msg = f"INVALID_TOOL_NAME: Proposed action '{action_name}' is not recognized or authorized within the safety scope."
            database.log_audit_entry(
                customer_id=customer_id,
                ml_risk_score=ml_risk_score,
                raw_llm_reasoning=raw_reasoning,
                proposed_action=action_name,
                action_params=params,
                guardrail_status="BLOCKED",
                policy_violation_reason=violation_msg,
                final_executed_action="NONE",
                execution_details={"error_code": "INVALID_TOOL_NAME", "message": violation_msg}
            )
            return {
                "guardrail_status": "BLOCKED",
                "policy_violation_reason": violation_msg,
                "executed_action": "NONE",
                "execution_details": {"error_code": "INVALID_TOOL_NAME", "message": violation_msg}
            }

        # --- GUARDRAIL CHECK 2: IDEMPOTENCY SAFETY ---
        if customer.get("processed") == 1:
            violation_msg = "IDEMPOTENCY_VIOLATION: Customer account has already been processed in a prior pipeline run. Action blocked to prevent duplicate interventions."
            database.log_audit_entry(
                customer_id=customer_id,
                ml_risk_score=ml_risk_score,
                raw_llm_reasoning=raw_reasoning,
                proposed_action=action_name,
                action_params=params,
                guardrail_status="BLOCKED",
                policy_violation_reason=violation_msg,
                final_executed_action="NONE",
                execution_details={"error_code": "IDEMPOTENCY_VIOLATION", "message": violation_msg}
            )
            return {
                "guardrail_status": "BLOCKED",
                "policy_violation_reason": violation_msg,
                "executed_action": "NONE",
                "execution_details": {"error_code": "IDEMPOTENCY_VIOLATION", "message": violation_msg}
            }

        policy_violations = []

        # --- GUARDRAIL CHECK 3: COUPON / DISCOUNT PERCENTAGE CAP ---
        if action_name in ["apply_razorpay_coupon", "offer_discount"]:
            pct = params.get("discount_percentage", params.get("percentage", 0))
            if pct > MAX_DISCOUNT_PERCENTAGE:
                policy_violations.append(
                    f"MAX_DISCOUNT_EXCEEDED: Proposed discount of {pct}% exceeds maximum authorized limit of {MAX_DISCOUNT_PERCENTAGE}%."
                )

            # --- GUARDRAIL CHECK 4: DOUBLE-DISCOUNT / COUPON POLICY ---
            if customer.get("has_discount") == 1:
                policy_violations.append(
                    "DOUBLE_DISCOUNT_PROHIBITED: Merchant already has an active coupon/discount on file. Stacking is strictly prohibited."
                )

            # --- GUARDRAIL CHECK 5: FINANCIAL LTV BOUNDARY ---
            duration = params.get("duration_months", 1)
            monthly_mrr = customer.get("mrr", 0)
            total_discount_cost = monthly_mrr * (pct / 100.0) * duration
            ltv_6mo = monthly_mrr * 6
            max_allowed_cost = ltv_6mo * LTV_MAX_INTERVENTION_RATIO

            if total_discount_cost > max_allowed_cost:
                policy_violations.append(
                    f"LTV_CAP_EXCEEDED: Total retention cost (₹{total_discount_cost:.2f}) exceeds 50% 6-month LTV cap (₹{max_allowed_cost:.2f})."
                )

        # --- GUARDRAIL CHECK 6: TRIAL EXTENSION LIMIT ---
        elif action_name == "extend_trial":
            days = params.get("days", 0)
            if days > MAX_TRIAL_EXTENSION_DAYS:
                policy_violations.append(
                    f"MAX_TRIAL_EXCEEDED: Proposed trial extension of {days} days exceeds maximum authorized limit of {MAX_TRIAL_EXTENSION_DAYS} days."
                )

        # --- GUARDRAIL CHECK 7: SUBSCRIPTION PAUSE LIMIT ---
        elif action_name == "pause_subscription":
            duration = params.get("duration_months", 0)
            if duration > MAX_PAUSE_DURATION_MONTHS:
                policy_violations.append(
                    f"MAX_PAUSE_EXCEEDED: Proposed pause duration of {duration} months exceeds maximum limit of {MAX_PAUSE_DURATION_MONTHS} months."
                )

        # --- VERDICT EVALUATION ---
        if not policy_violations:
            # Policy Passed -> Execute Action
            exec_result = GuardrailInterceptor._dispatch_action(
                customer_id, action_name, params, simulate_error=simulate_api_error, simulate_rate_limit=simulate_rate_limit
            )

            # Handle simulated API errors cleanly
            if exec_result.get("status") in ["RATE_LIMITED", "GATEWAY_ERROR"]:
                database.log_audit_entry(
                    customer_id=customer_id,
                    ml_risk_score=ml_risk_score,
                    raw_llm_reasoning=raw_reasoning,
                    proposed_action=action_name,
                    action_params=params,
                    guardrail_status="API_ERROR_RETRY",
                    policy_violation_reason=exec_result.get("message"),
                    final_executed_action="NONE",
                    execution_details=exec_result
                )
                return {
                    "guardrail_status": "API_ERROR_RETRY",
                    "policy_violation_reason": exec_result.get("message"),
                    "executed_action": "NONE",
                    "execution_details": exec_result
                }

            database.mark_customer_processed(customer_id, new_status="RETAINED")
            database.log_audit_entry(
                customer_id=customer_id,
                ml_risk_score=ml_risk_score,
                raw_llm_reasoning=raw_reasoning,
                proposed_action=action_name,
                action_params=params,
                guardrail_status="APPROVED",
                policy_violation_reason=None,
                final_executed_action=action_name,
                execution_details=exec_result
            )
            return {
                "guardrail_status": "APPROVED",
                "policy_violation_reason": None,
                "executed_action": action_name,
                "execution_details": exec_result
            }

        else:
            # Policy Violated -> Handle Block or Auto-Remediation
            violation_summary = " | ".join(policy_violations)

            if auto_remediate_violators and action_name in ["apply_razorpay_coupon", "offer_discount"] and customer.get("has_discount") == 0:
                remediated_params = dict(params)
                if "discount_percentage" in remediated_params:
                    remediated_params["discount_percentage"] = int(MAX_DISCOUNT_PERCENTAGE)
                if "percentage" in remediated_params:
                    remediated_params["percentage"] = int(MAX_DISCOUNT_PERCENTAGE)
                
                exec_result = GuardrailInterceptor._dispatch_action(customer_id, action_name, remediated_params)
                database.mark_customer_processed(customer_id, new_status="RETAINED_REMEDIATED")
                
                remediate_note = f"AUTO_REMEDIATED: Capped coupon/discount to {MAX_DISCOUNT_PERCENTAGE}%. Original violations: {violation_summary}"
                database.log_audit_entry(
                    customer_id=customer_id,
                    ml_risk_score=ml_risk_score,
                    raw_llm_reasoning=raw_reasoning,
                    proposed_action=action_name,
                    action_params=params,
                    guardrail_status="AUTO_REMEDIATED",
                    policy_violation_reason=remediate_note,
                    final_executed_action=action_name,
                    execution_details=exec_result
                )
                return {
                    "guardrail_status": "AUTO_REMEDIATED",
                    "policy_violation_reason": remediate_note,
                    "executed_action": action_name,
                    "execution_details": exec_result
                }

            # Strictly Block Action
            database.log_audit_entry(
                customer_id=customer_id,
                ml_risk_score=ml_risk_score,
                raw_llm_reasoning=raw_reasoning,
                proposed_action=action_name,
                action_params=params,
                guardrail_status="BLOCKED",
                policy_violation_reason=violation_summary,
                final_executed_action="NONE",
                execution_details={"blocked_policy_reason": violation_summary}
            )
            return {
                "guardrail_status": "BLOCKED",
                "policy_violation_reason": violation_summary,
                "executed_action": "NONE",
                "execution_details": {"blocked_policy_reason": violation_summary}
            }

    @staticmethod
    def _dispatch_action(customer_id, action_name, params, simulate_error=False, simulate_rate_limit=False):
        """Dispatches approved tool call to MockRazorpayAPI."""
        if action_name == "razorpay_smart_retry":
            return MockRazorpayAPI.razorpay_smart_retry(customer_id, params.get("gateway_priority", "OPTIMUS_HIGH"))
        elif action_name == "create_razorpay_payment_link":
            return MockRazorpayAPI.create_razorpay_payment_link(customer_id, params.get("amount_inr", 1000), params.get("expires_in_hours", 24))
        elif action_name in ["apply_razorpay_coupon", "offer_discount"]:
            pct = params.get("discount_percentage", params.get("percentage", 10))
            return MockRazorpayAPI.apply_razorpay_coupon(
                customer_id, pct, params.get("duration_months", 3),
                simulate_error=simulate_error, simulate_rate_limit=simulate_rate_limit
            )
        elif action_name == "send_whatsapp_payment_reminder":
            return MockRazorpayAPI.send_whatsapp_payment_reminder(customer_id, params.get("template_id", "PAYMENT_DUNNING_WHATSAPP"))
        elif action_name == "pause_subscription":
            return MockRazorpayAPI.pause_subscription(customer_id, params.get("duration_months", 1))
        elif action_name == "extend_trial":
            return MockRazorpayAPI.extend_trial(customer_id, params.get("days", 7))
        else:
            return {"status": "ERROR", "error_code": "UNKNOWN_ACTION", "message": f"Unknown action '{action_name}'"}
