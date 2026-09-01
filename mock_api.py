import database
import uuid

class MockBillingAPI:
    """
    Simulates Payment Gateway & Subscriptions API endpoints:
    - Smart Retry engine (with exponential backoff)
    - UPI AutoPay Mandate Creation
    - Instant Recovery Payment Links
    - Subscription Coupon Applications
    - WhatsApp / SMS Payment Dunning Reminders
    - Mandate Pausing & CSM Escalations
    """
    @staticmethod
    def trigger_smart_retry(customer_id, gateway_priority="HIGH"):
        payment_id = f"pay_{uuid.uuid4().hex[:10]}"
        return {
            "status": "SUCCESS",
            "action": "SMART_RETRY_TRIGGERED",
            "payment_id": payment_id,
            "gateway_priority": gateway_priority,
            "retry_schedule": "Exponential Backoff (T+1h, T+6h, T+24h)",
            "message": f"Triggered Smart Retry for merchant {customer_id}. Payment ID: {payment_id}."
        }

    @staticmethod
    def enable_upi_autopay_mandate(customer_id, vpa_handle=None):
        vpa_handle = vpa_handle or f"{customer_id.lower()}@upi"
        mandate_id = f"umn_{uuid.uuid4().hex[:10]}"
        
        # Update mandate status in database
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET mandate_status = 'ACTIVE' WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()

        return {
            "status": "SUCCESS",
            "action": "UPI_AUTOPAY_ENABLED",
            "mandate_id": mandate_id,
            "vpa_handle": vpa_handle,
            "message": f"Successfully enabled UPI AutoPay Mandate ({mandate_id}) for merchant {customer_id} via VPA {vpa_handle}."
        }

    @staticmethod
    def create_recovery_payment_link(customer_id, amount_inr, expires_in_hours=24):
        plink_id = f"plink_{uuid.uuid4().hex[:10]}"
        short_url = f"https://pay.gateway.io/i/{plink_id}"
        return {
            "status": "SUCCESS",
            "action": "PAYMENT_LINK_CREATED",
            "payment_link_id": plink_id,
            "payment_link_url": short_url,
            "amount_inr": amount_inr,
            "message": f"Generated Instant Recovery Payment Link ({short_url}) for ₹{amount_inr}."
        }

    @staticmethod
    def apply_retention_coupon(customer_id, discount_percentage, duration_months=3, simulate_error=False, simulate_rate_limit=False):
        if simulate_rate_limit:
            return {
                "status": "RATE_LIMITED",
                "error_code": "GATEWAY_429_TOO_MANY_REQUESTS",
                "message": "Subscriptions API rate limit encountered (HTTP 429). Action scheduled for automatic retry.",
                "retry_recommended": True
            }
        
        if simulate_error:
            return {
                "status": "GATEWAY_ERROR",
                "error_code": "GATEWAY_500_INTERNAL_ERROR",
                "message": "API Gateway 500 Error. Fallback: Alerted engineering team.",
                "retry_recommended": True
            }

        customer = database.get_customer_by_id(customer_id)
        if not customer:
            return {"status": "ERROR", "error_code": "CUSTOMER_NOT_FOUND", "message": f"Merchant {customer_id} not found."}
        
        # Apply coupon in database
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET has_discount = 1 WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()

        saved_arr_inr = round(customer["mrr"] * 12 * (discount_percentage / 100.0), 2)
        coupon_code = f"RETENTION_{int(discount_percentage)}"
        return {
            "status": "SUCCESS",
            "action": "COUPON_APPLIED",
            "coupon_code": coupon_code,
            "message": f"Applied Coupon '{coupon_code}' ({discount_percentage}% off) to merchant {customer_id}.",
            "saved_annual_revenue_inr": saved_arr_inr
        }

    @staticmethod
    def send_whatsapp_payment_reminder(customer_id, template_id="PAYMENT_DUNNING_WHATSAPP"):
        return {
            "status": "SUCCESS",
            "action": "WHATSAPP_REMINDER_SENT",
            "template_id": template_id,
            "message": f"Dispatched WhatsApp Payment Dunning Reminder ('{template_id}') to merchant {customer_id}."
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
            "message": f"Paused subscription mandate for merchant {customer_id} for {duration_months} months."
        }

    @staticmethod
    def extend_trial(customer_id, days):
        return {
            "status": "SUCCESS",
            "action": "TRIAL_EXTENDED",
            "message": f"Extended subscription trial for merchant {customer_id} by {days} days."
        }
