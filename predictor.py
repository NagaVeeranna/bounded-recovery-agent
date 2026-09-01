import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import database

RISK_TRIGGER_THRESHOLD = 75.0  # 75% risk threshold triggers LLM reasoning engine

class ChurnPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False

    def generate_training_dataset(self, num_samples=500):
        """
        Generates synthetic historical training data based on fintech churn patterns.
        """
        np.random.seed(42)

        days_since_active = np.random.exponential(scale=10, size=num_samples)
        days_since_active = np.clip(days_since_active, 0, 60)

        failed_payment_count = np.random.choice([0, 1, 2, 3], size=num_samples, p=[0.7, 0.15, 0.1, 0.05])
        support_tickets_30d = np.random.poisson(lam=1.2, size=num_samples)
        usage_drop_pct = np.random.uniform(0, 100, size=num_samples)
        card_expiring_soon = np.random.choice([0, 1], size=num_samples, p=[0.8, 0.2])

        # True risk formula for generating binary target ground truth
        risk_score_raw = (
            (days_since_active / 30.0) * 40.0 +
            failed_payment_count * 20.0 +
            (support_tickets_30d / 5.0) * 15.0 +
            (usage_drop_pct / 100.0) * 25.0 +
            card_expiring_soon * 30.0
        )
        
        # Binary target: Churned = 1 if risk > 70
        churned = (risk_score_raw >= 65.0).astype(int)

        df = pd.DataFrame({
            "days_since_active": days_since_active,
            "failed_payment_count": failed_payment_count,
            "support_tickets_30d": support_tickets_30d,
            "usage_drop_pct": usage_drop_pct,
            "card_expiring_soon": card_expiring_soon,
            "churned": churned
        })
        return df

    def train(self):
        """Trains the ML model on synthetic behavioral history."""
        df = self.generate_training_dataset()
        X = df[["days_since_active", "failed_payment_count", "support_tickets_30d", "usage_drop_pct", "card_expiring_soon"]]
        y = df["churned"]

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        print("[Predictive Engine] ML Classifier model trained successfully.")

    def predict_risk_score(self, customer):
        """
        Calculates a deterministic risk score (0 - 100%) for a given customer profile.
        """
        if not self.is_trained:
            self.train()

        features = np.array([[
            float(customer["days_since_active"]),
            float(customer["failed_payment_count"]),
            float(customer["support_tickets_30d"]),
            float(customer["usage_drop_pct"]),
            float(customer["card_expiring_soon"])
        ]])

        features_scaled = self.scaler.transform(features)
        
        # Get probability of churn from ML classifier
        probability_churn = self.model.predict_proba(features_scaled)[0][1]
        
        # Combine model probability with domain rules (e.g. card expiring + failed payments)
        domain_boost = 0.0
        if customer["card_expiring_soon"] == 1 and customer["failed_payment_count"] > 0:
            domain_boost += 0.25 # Significant payment default risk
        if customer["days_since_active"] > 25 and customer["usage_drop_pct"] > 80:
            domain_boost += 0.30 # Complete ghosting risk

        final_risk_score = round(min(100.0, (probability_churn + domain_boost) * 100.0), 2)
        return final_risk_score

def run_predictive_pipeline():
    """
    Evaluates all customers in the database, updates their risk scores,
    and returns customers crossing the > 75% trigger threshold.
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
        risk_status = "AT_RISK" if risk_score >= RISK_TRIGGER_THRESHOLD else "HEALTHY"
        
        database.update_customer_risk(c["id"], risk_score, risk_status)
        c["risk_score"] = risk_score
        c["risk_status"] = risk_status

        status_flag = "[TRIGGERED -> PASS TO AGENT]" if risk_score >= RISK_TRIGGER_THRESHOLD else "[HEALTHY -> FILTERED OUT]"
        print(f"Customer {c['id']} ({c['name']}): Risk Score = {risk_score}% | Status: {risk_status} {status_flag}")

        if risk_score >= RISK_TRIGGER_THRESHOLD:
            at_risk_customers.append(c)

    print(f"\n[Predictive Engine] Summary: {len(at_risk_customers)} out of {len(customers)} customers passed threshold (> {RISK_TRIGGER_THRESHOLD}%).")
    return at_risk_customers

if __name__ == "__main__":
    database.seed_synthetic_data()
    run_predictive_pipeline()
