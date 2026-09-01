import os

class Config:
    """
    Centralized configuration management with environment variable overrides.
    """
    # Policy Guardrail Bounds
    MAX_DISCOUNT_PERCENTAGE: float = float(os.getenv("MAX_DISCOUNT_PERCENTAGE", "15.0"))
    MAX_TRIAL_EXTENSION_DAYS: int = int(os.getenv("MAX_TRIAL_EXTENSION_DAYS", "14"))
    MAX_PAUSE_DURATION_MONTHS: int = int(os.getenv("MAX_PAUSE_DURATION_MONTHS", "3"))
    LTV_MAX_INTERVENTION_RATIO: float = float(os.getenv("LTV_MAX_INTERVENTION_RATIO", "0.50"))

    # Predictive Trigger Threshold
    RISK_TRIGGER_THRESHOLD: float = float(os.getenv("RISK_TRIGGER_THRESHOLD", "75.0"))

    # Razorpay API & Webhook Config
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock12345")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "mock_secret_key_12345")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "whsec_mock_razorpay_secret")

    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
