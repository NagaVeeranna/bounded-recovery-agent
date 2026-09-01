import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import database
from config import Config

class ChurnPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False

    def generate_training_dataset(self, num_samples=500):
        """
        Generates synthetic historical training data tailored to merchant payment behaviors:
        Features: payment_failure_rate, days_since_last_transaction, failed_payment_count, card_expiring_soon, avg_transaction_value.
        """
        np.random.seed(42)

        days_since_last_transaction = np.random.exponential(scale=12, size=num_samples)
        days_since_last_transaction = np.clip(days_since_last_transaction, 0, 60)

        payment_failure_rate = np.random.uniform(0.0, 1.0, size=num_samples)
        failed_payment_count = np.random.choice([0, 1, 2, 3, 4], size=num_samples, p=[0.6, 0.2, 0.1, 0.06, 0.04])
        card_expiring_soon = np.random.choice([0, 1], size=num_samples, p=[0.8, 0.2])
        avg_transaction_value = np.random.uniform(500, 50000, size=num_samples)

        # True risk formula for generating churn ground truth
        risk_score_raw = (
            (days_since_last_transaction / 30.0) * 35.0 +
            (payment_failure_rate) * 40.0 +
            failed_payment_count * 15.0 +
            card_expiring_soon * 25.0
        )
        
        # Binary target: Churned = 1 if risk >= 65.0
        churned = (risk_score_raw >= 65.0).astype(int)

        df = pd.DataFrame({
            "days_since_last_transaction": days_since_last_transaction,
            "payment_failure_rate": payment_failure_rate,
            "failed_payment_count": failed_payment_count,
            "card_expiring_soon": card_expiring_soon,
            "avg_transaction_value": avg_transaction_value,
            "churned": churned
        })
        return df

    def train(self):
        """Trains the ML model on synthetic payment behavioral data."""
        df = self.generate_training_dataset()
        X = df[["days_since_last_transaction", "payment_failure_rate", "failed_payment_count", "card_expiring_soon", "avg_transaction_value"]]
        y = df["churned"]

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        print("[Predictive Engine] ML Classifier model trained successfully.")

    def predict_risk_score(self, customer):
        """
        Calculates a deterministic risk score (0 - 100%) for a given merchant profile.
        """
        if not self.is_trained:
            self.train()

        features = pd.DataFrame([{
            "days_since_last_transaction": float(customer["days_since_last_transaction"]),
            "payment_failure_rate": float(customer["payment_failure_rate"]),
            "failed_payment_count": float(customer["failed_payment_count"]),
            "card_expiring_soon": float(customer["card_expiring_soon"]),
            "avg_transaction_value": float(customer["avg_transaction_value"])
        }])

        features_scaled = self.scaler.transform(features)
        
        # Get probability of churn from ML classifier
        probability_churn = self.model.predict_proba(features_scaled)[0][1]
        
        # Domain rules (Mandate & Payment Failure Boost)
        domain_boost = 0.0
        if customer.get("mandate_status") == "FAILED_RETRY" or (customer["card_expiring_soon"] == 1 and customer["failed_payment_count"] > 0):
            domain_boost += 0.25 # Significant payment default risk
        if customer["days_since_last_transaction"] > 25 and customer["payment_failure_rate"] > 0.70:
            domain_boost += 0.30 # Complete merchant transaction drop-off

        final_risk_score = round(min(100.0, (probability_churn + domain_boost) * 100.0), 2)
        return final_risk_score

def run_predictive_pipeline():
    """
    Evaluates all merchant accounts in the database, updates risk scores,
    and returns accounts crossing the > 75% trigger threshold.
    """
    predictor = ChurnPredictor()
    predictor.train()

    customers = database.get_all_customers()
    at_risk_customers = []

    print("\n=======================================================")
    print("   LAYER 2: PREDICTIVE ENGINE EVALUATION (0 - 100%)    ")
    print("=======================================================")

    for c in customers:
        risk_score = predictor.predict_risk_score(c)
        risk_status = "AT_RISK" if risk_score >= Config.RISK_TRIGGER_THRESHOLD else "HEALTHY"
        
        database.update_customer_risk(c["id"], risk_score, risk_status)
        c["risk_score"] = risk_score
        c["risk_status"] = risk_status

        status_flag = "[TRIGGERED -> PASS TO AGENT]" if risk_score >= Config.RISK_TRIGGER_THRESHOLD else "[HEALTHY -> FILTERED OUT]"
        print(f"Merchant {c['id']} ({c['name']}): Risk Score = {risk_score}% | Category: {c['merchant_category']} | Status: {risk_status} {status_flag}")

        if risk_score >= Config.RISK_TRIGGER_THRESHOLD:
            at_risk_customers.append(c)

    print(f"\n[Predictive Engine] Summary: {len(at_risk_customers)} out of {len(customers)} accounts passed threshold (> {Config.RISK_TRIGGER_THRESHOLD}%).")
    return at_risk_customers

if __name__ == "__main__":
    database.seed_synthetic_data()
    run_predictive_pipeline()
