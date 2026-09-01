import database

class MockBillingAPI:
    """
    Simulates external billing gateways (Stripe / Chargebee) and CRM system mutations,
    including rate-limit handling, 500 error retries, and clean fallbacks.
    """
    @staticmethod
    def apply_discount(customer_id, percentage, duration_months, simulate_error=False, simulate_rate_limit=False):
        # Handle simulated rate limit or 500 server error
        if simulate_rate_limit:
            return {
                "status": "RATE_LIMITED",
                "error_code": "STRIPE_429_TOO_MANY_REQUESTS",
                "message": "Stripe API rate limit encountered (HTTP 429). Action scheduled for automatic retry.",
                "retry_recommended": True
            }
        
        if simulate_error:
            return {
                "status": "GATEWAY_ERROR",
                "error_code": "STRIPE_500_INTERNAL_ERROR",
                "message": "Stripe Gateway 500 Error. Fallback: Logged issue and alerted engineering team.",
                "retry_recommended": True
            }

        customer = database.get_customer_by_id(customer_id)
        if not customer:
            return {"status": "ERROR", "error_code": "CUSTOMER_NOT_FOUND", "message": f"Customer {customer_id} not found."}
        
        # Apply discount in database
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET has_discount = 1 WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()

        saved_arr = round(customer["mrr"] * 12 * (percentage / 100.0), 2)
        return {
            "status": "SUCCESS",
            "action": "DISCOUNT_APPLIED",
            "message": f"Applied {percentage}% discount for {duration_months} months to account {customer_id}.",
            "saved_annual_revenue": saved_arr
        }

    @staticmethod
    def extend_trial(customer_id, days):
        return {
            "status": "SUCCESS",
            "action": "TRIAL_EXTENDED",
            "message": f"Extended trial for customer {customer_id} by {days} days."
        }

    @staticmethod
    def pause_subscription(customer_id, duration_months):
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET status = 'PAUSED' WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()

        return {
            "status": "SUCCESS",
            "action": "SUBSCRIPTION_PAUSED",
            "message": f"Paused subscription for customer {customer_id} for {duration_months} months."
        }

    @staticmethod
    def send_retention_email(customer_id, template_id, customized_note):
        return {
            "status": "SUCCESS",
            "action": "EMAIL_DISPATCHED",
            "message": f"Dispatched email '{template_id}' to customer {customer_id}. Note: '{customized_note}'"
        }

    @staticmethod
    def schedule_customer_success_call(customer_id, urgency):
        return {
            "status": "SUCCESS",
            "action": "CSM_CALL_SCHEDULED",
            "message": f"Scheduled {urgency} urgency CSM retention call for account {customer_id}."
        }
