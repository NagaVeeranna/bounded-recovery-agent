import database
from mock_api import MockBillingAPI

# --- HARDCODED COMPANY FINANCIAL & OPERATIONAL POLICIES ---
MAX_DISCOUNT_PERCENTAGE = 20.0       # Max discount allowed without CFO approval
MAX_TRIAL_EXTENSION_DAYS = 14        # Max trial extension allowed
MAX_PAUSE_DURATION_MONTHS = 3        # Max subscription pause allowed
LTV_MAX_INTERVENTION_RATIO = 0.50   # Max cost allowed is 50% of 6-month LTV

class GuardrailInterceptor:
    """
    Evaluates raw LLM proposed retention actions against deterministic company policies
    BEFORE allowing interaction with billing APIs or databases.
    """
    @staticmethod
    def evaluate_and_execute(customer, llm_output, auto_remediate_violators=False):
        customer_id = customer["id"]
        ml_risk_score = customer.get("risk_score", 0.0)
        raw_reasoning = llm_output.get("reasoning", "No reasoning provided.")
        tool_call = llm_output.get("tool_call", {})

        action_name = tool_call.get("name", "UNKNOWN_ACTION")
        params = tool_call.get("parameters", {})

        # --- GUARDRAIL CHECK 1: IDEMPOTENCY SAFETY ---
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
                execution_details={"error": violation_msg}
            )
            return {
                "guardrail_status": "BLOCKED",
                "policy_violation_reason": violation_msg,
                "executed_action": "NONE",
                "execution_details": None
            }

        policy_violations = []

        # --- GUARDRAIL CHECK 2: DISCOUNT PERCENTAGE CAP ---
        if action_name == "offer_discount":
            pct = params.get("percentage", 0)
            if pct > MAX_DISCOUNT_PERCENTAGE:
                policy_violations.append(
                    f"MAX_DISCOUNT_EXCEEDED: Proposed discount of {pct}% exceeds maximum authorized limit of {MAX_DISCOUNT_PERCENTAGE}%."
                )

            # --- GUARDRAIL CHECK 3: DOUBLE-DISCOUNT POLICY ---
            if customer.get("has_discount") == 1:
                policy_violations.append(
                    "DOUBLE_DISCOUNT_PROHIBITED: Customer already has an active discount on file. Discount stacking is strictly prohibited."
                )

            # --- GUARDRAIL CHECK 4: FINANCIAL LTV BOUNDARY ---
            duration = params.get("duration_months", 1)
            monthly_mrr = customer.get("mrr", 0)
            total_discount_cost = monthly_mrr * (pct / 100.0) * duration
            ltv_6mo = monthly_mrr * 6
            max_allowed_cost = ltv_6mo * LTV_MAX_INTERVENTION_RATIO

            if total_discount_cost > max_allowed_cost:
                policy_violations.append(
                    f"LTV_CAP_EXCEEDED: Total retention cost (${total_discount_cost:.2f}) exceeds 50% 6-month LTV cap (${max_allowed_cost:.2f})."
                )

        # --- GUARDRAIL CHECK 5: TRIAL EXTENSION LIMIT ---
        elif action_name == "extend_trial":
            days = params.get("days", 0)
            if days > MAX_TRIAL_EXTENSION_DAYS:
                policy_violations.append(
                    f"MAX_TRIAL_EXCEEDED: Proposed trial extension of {days} days exceeds maximum authorized limit of {MAX_TRIAL_EXTENSION_DAYS} days."
                )

        # --- GUARDRAIL CHECK 6: SUBSCRIPTION PAUSE LIMIT ---
        elif action_name == "pause_subscription":
            duration = params.get("duration_months", 0)
            if duration > MAX_PAUSE_DURATION_MONTHS:
                policy_violations.append(
                    f"MAX_PAUSE_EXCEEDED: Proposed pause duration of {duration} months exceeds maximum limit of {MAX_PAUSE_DURATION_MONTHS} months."
                )

        # --- VERDICT EVALUATION ---
        if not policy_violations:
            # Policy Passed -> Execute Action
            exec_result = GuardrailInterceptor._dispatch_action(customer_id, action_name, params)
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

            if auto_remediate_violators and action_name == "offer_discount" and customer.get("has_discount") == 0:
                # Remediation: Cap discount percentage at 20%
                remediated_params = dict(params)
                remediated_params["percentage"] = int(MAX_DISCOUNT_PERCENTAGE)
                
                exec_result = GuardrailInterceptor._dispatch_action(customer_id, action_name, remediated_params)
                database.mark_customer_processed(customer_id, new_status="RETAINED_REMEDIATED")
                
                remediate_note = f"AUTO_REMEDIATED: Capped discount from {params.get('percentage')}% to {MAX_DISCOUNT_PERCENTAGE}%. Original violations: {violation_summary}"
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
    def _dispatch_action(customer_id, action_name, params):
        """Dispatches approved tool call to the Mock Billing API."""
        if action_name == "offer_discount":
            return MockBillingAPI.apply_discount(customer_id, params.get("percentage", 10), params.get("duration_months", 3))
        elif action_name == "extend_trial":
            return MockBillingAPI.extend_trial(customer_id, params.get("days", 7))
        elif action_name == "pause_subscription":
            return MockBillingAPI.pause_subscription(customer_id, params.get("duration_months", 1))
        elif action_name == "send_retention_email":
            return MockBillingAPI.send_retention_email(customer_id, params.get("template_id", "GENERAL_DUNNING"), params.get("customized_note", ""))
        elif action_name == "schedule_customer_success_call":
            return MockBillingAPI.schedule_customer_success_call(customer_id, params.get("urgency", "MEDIUM"))
        else:
            return {"status": "ERROR", "message": f"Unknown action '{action_name}'"}
