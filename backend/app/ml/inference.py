from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd


DEFAULT_MODEL_PATH = os.getenv("MODEL_PATH", "models/recovery_model.joblib")

CATEGORICAL_FEATURES = [
    "payment_method",
    "gateway",
    "failure_category",
    "failure_code",
    "preferred_payment_method",
    "device_type",
]

NUMERICAL_FEATURES = [
    "amount",
    "attempt_number",
    "customer_transaction_count",
    "customer_success_rate",
    "customer_average_transaction",
    "risk_score",
    "checkout_duration",
    "hour",
    "historical_failure_count",
]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES


class RecoveryPredictor:
    """Production inference engine for predicting transaction recovery probability."""

    _instance: Optional[RecoveryPredictor] = None

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.bundle: Optional[Dict[str, Any]] = None
        self.load_model()

    @classmethod
    def get_instance(cls, model_path: str = DEFAULT_MODEL_PATH) -> RecoveryPredictor:
        if cls._instance is None or cls._instance.model_path != model_path:
            cls._instance = cls(model_path=model_path)
        return cls._instance

    def load_model(self) -> None:
        """Loads serialized XGBoost model bundle from disk."""
        if os.path.exists(self.model_path):
            try:
                self.bundle = joblib.load(self.model_path)
            except Exception as e:
                print(f"Warning: Failed to load model from {self.model_path}: {e}")
                self.bundle = None
        else:
            self.bundle = None

    def extract_features(self, transaction: Dict[str, Any]) -> pd.DataFrame:
        """Extracts and normalizes the 15 input features from a transaction dictionary."""
        amount = float(transaction.get("amount", 1000.0))
        payment_method = str(transaction.get("payment_method", "UPI")).upper()
        gateway = str(transaction.get("gateway", "GATEWAY_A")).upper()
        failure_code = str(transaction.get("failure_code") or transaction.get("failure_type") or "GATEWAY_TIMEOUT").upper()
        failure_category = str(transaction.get("failure_category", "TEMPORARY")).upper()
        attempt_number = int(transaction.get("attempt_number", 1))

        # Customer features (with sensible cold-start defaults)
        cust_txns = int(transaction.get("customer_transaction_count", transaction.get("total_transactions", 10)))
        cust_success_rate = float(transaction.get("customer_success_rate", transaction.get("success_rate", 0.85)))
        cust_avg_amount = float(transaction.get("customer_average_transaction", transaction.get("average_transaction_amount", amount)))
        preferred_method = str(transaction.get("preferred_payment_method", payment_method)).upper()
        hist_failures = int(transaction.get("historical_failure_count", transaction.get("failed_transactions", 1)))

        risk_score = float(transaction.get("risk_score", 0.15))
        checkout_duration = float(transaction.get("checkout_duration", 120.0))
        device_type = str(transaction.get("device_type", "MOBILE")).upper()

        # Extract hour from timestamp or current time
        created_at_raw = transaction.get("created_at")
        if isinstance(created_at_raw, str):
            try:
                hour = datetime.fromisoformat(created_at_raw).hour
            except Exception:
                hour = 14
        elif isinstance(created_at_raw, datetime):
            hour = created_at_raw.hour
        else:
            hour = int(transaction.get("hour", 14))

        feature_dict = {
            "amount": amount,
            "payment_method": payment_method,
            "gateway": gateway,
            "failure_category": failure_category,
            "failure_code": failure_code,
            "attempt_number": attempt_number,
            "customer_transaction_count": cust_txns,
            "customer_success_rate": cust_success_rate,
            "customer_average_transaction": cust_avg_amount,
            "preferred_payment_method": preferred_method,
            "risk_score": risk_score,
            "checkout_duration": checkout_duration,
            "device_type": device_type,
            "hour": hour,
            "historical_failure_count": hist_failures,
        }

        return pd.DataFrame([feature_dict])

    def get_top_features(self, top_k: int = 5) -> List[Dict[str, Any]]:
        """Returns the top global important features from the trained XGBoost model."""
        if self.bundle and "raw_model" in self.bundle:
            raw_model = self.bundle["raw_model"]
            feature_names = self.bundle.get("transformed_feature_names", [])
            if hasattr(raw_model, "feature_importances_"):
                importances = raw_model.feature_importances_
                indices = np.argsort(importances)[::-1][:top_k]
                return [
                    {
                        "feature": feature_names[idx] if idx < len(feature_names) else f"feature_{idx}",
                        "importance": round(float(importances[idx]), 4),
                    }
                    for idx in indices
                ]

        # Default fallback importance weights if model not yet trained
        return [
            {"feature": "failure_code", "importance": 0.32},
            {"feature": "failure_category", "importance": 0.24},
            {"feature": "risk_score", "importance": 0.18},
            {"feature": "customer_success_rate", "importance": 0.14},
            {"feature": "amount", "importance": 0.12},
        ]

    def predict(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Predicts recovery probability and provides explainability features."""
        df_features = self.extract_features(transaction)

        if self.bundle and "calibrated_model" in self.bundle and "preprocessor" in self.bundle:
            preprocessor = self.bundle["preprocessor"]
            model = self.bundle["calibrated_model"]

            X_proc = preprocessor.transform(df_features)
            prob = float(model.predict_proba(X_proc)[0, 1])
            model_version = self.bundle.get("model_version", "1.0.0-xgb")
        else:
            # Domain-heuristic fallback if model artifact is unavailable
            failure_code = df_features["failure_code"].iloc[0]
            risk = df_features["risk_score"].iloc[0]
            success_rate = df_features["customer_success_rate"].iloc[0]

            if failure_code in {"GATEWAY_TIMEOUT", "AUTH_TIMEOUT", "OTP_FAILURE"}:
                base = 0.75
            elif failure_code in {"BANK_UNAVAILABLE", "CUSTOMER_ABANDONED"}:
                base = 0.55
            elif failure_code in {"CARD_DECLINED"}:
                base = 0.35
            elif failure_code in {"CARD_EXPIRED", "INSUFFICIENT_FUNDS"}:
                base = 0.10
            elif failure_code in {"HIGH_RISK", "DUPLICATE_PAYMENT"}:
                base = 0.01
            else:
                base = 0.40

            prob = float(np.clip(base + 0.15 * (success_rate - 0.5) - 0.25 * risk, 0.01, 0.99))
            model_version = "fallback-heuristic"

        important_features = self.get_top_features(top_k=5)

        return {
            "probability": round(prob, 4),
            "model_version": model_version,
            "important_features": important_features,
            "predicted_label": 1 if prob >= 0.5 else 0,
        }

    def predict_batch(self, transactions: List[Dict[str, Any]]) -> List[float]:
        """Vectorized batch prediction for high-throughput simulations."""
        if not transactions:
            return []

        feature_dicts = []
        for t in transactions:
            amount = float(t.get("amount", 1000.0))
            payment_method = str(t.get("payment_method", "UPI")).upper()
            gateway = str(t.get("gateway", "GATEWAY_A")).upper()
            failure_code = str(t.get("failure_code") or t.get("failure_type") or "GATEWAY_TIMEOUT").upper()
            failure_category = str(t.get("failure_category", "TEMPORARY")).upper()
            attempt_number = int(t.get("attempt_number", 1))

            cust_txns = int(t.get("customer_transaction_count", t.get("total_transactions", 10)))
            cust_success_rate = float(t.get("customer_success_rate", t.get("success_rate", 0.85)))
            cust_avg_amount = float(t.get("customer_average_transaction", t.get("average_transaction_amount", amount)))
            preferred_method = str(t.get("preferred_payment_method", payment_method)).upper()
            hist_failures = int(t.get("historical_failure_count", t.get("failed_transactions", 1)))

            risk_score = float(t.get("risk_score", 0.15))
            checkout_duration = float(t.get("checkout_duration", 120.0))
            device_type = str(t.get("device_type", "MOBILE")).upper()
            hour = int(t.get("hour", 14))

            feature_dicts.append({
                "amount": amount,
                "payment_method": payment_method,
                "gateway": gateway,
                "failure_category": failure_category,
                "failure_code": failure_code,
                "attempt_number": attempt_number,
                "customer_transaction_count": cust_txns,
                "customer_success_rate": cust_success_rate,
                "customer_average_transaction": cust_avg_amount,
                "preferred_payment_method": preferred_method,
                "risk_score": risk_score,
                "checkout_duration": checkout_duration,
                "device_type": device_type,
                "hour": hour,
                "historical_failure_count": hist_failures,
            })

        df = pd.DataFrame(feature_dicts)
        if self.bundle and "calibrated_model" in self.bundle and "preprocessor" in self.bundle:
            preprocessor = self.bundle["preprocessor"]
            model = self.bundle["calibrated_model"]
            X_proc = preprocessor.transform(df)
            probs = model.predict_proba(X_proc)[:, 1]
            return [round(float(p), 4) for p in probs]

        return [round(float(np.clip(0.65 - 0.3 * d["risk_score"], 0.01, 0.99)), 4) for d in feature_dicts]


def predict_recovery_probability(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Top-level prediction entrypoint for recovery probability prediction."""
    predictor = RecoveryPredictor.get_instance()
    return predictor.predict(transaction)


def predict_batch_recovery_probabilities(transactions: List[Dict[str, Any]]) -> List[float]:
    """Top-level batch prediction entrypoint for high-speed simulation."""
    predictor = RecoveryPredictor.get_instance()
    return predictor.predict_batch(transactions)

