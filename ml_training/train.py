import argparse
import csv
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier


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


def infer_device_type(payment_method: str, cust_id: str) -> str:
    """Deterministically infers user session device without post-event leakage."""
    h = hash(cust_id) % 100
    if payment_method == "UPI":
        return "MOBILE" if h < 92 else "DESKTOP"
    elif payment_method == "NETBANKING":
        return "DESKTOP" if h < 75 else ("MOBILE" if h < 92 else "TABLET")
    elif payment_method == "CARD":
        return "MOBILE" if h < 65 else ("DESKTOP" if h < 90 else "TABLET")
    else:  # WALLET
        return "MOBILE" if h < 85 else "DESKTOP"


def load_and_engineer_features(data_dir: str) -> Tuple[pd.DataFrame, pd.Series]:
    """Loads raw data tables and extracts 15 leak-free features for the recovery population."""
    print("Loading data tables from:", data_dir)

    txn_path = os.path.join(data_dir, "transactions.csv")
    cust_path = os.path.join(data_dir, "customers.csv")
    att_path = os.path.join(data_dir, "payment_attempts.csv")
    chk_path = os.path.join(data_dir, "checkout_sessions.csv")

    # Load lookup dictionaries to minimize join overhead
    customers_map: Dict[str, Dict[str, Any]] = {}
    with open(cust_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            customers_map[row["customer_id"]] = row

    checkout_map: Dict[str, Dict[str, Any]] = {}
    with open(chk_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            txn_ref = row["transaction_id"]
            if txn_ref:
                checkout_map[txn_ref] = row

    attempts_by_txn: Dict[str, List[Dict[str, Any]]] = {}
    with open(att_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            attempts_by_txn.setdefault(row["transaction_id"], []).append(row)

    rows: List[Dict[str, Any]] = []
    targets: List[int] = []

    with open(txn_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            txn_id = row["transaction_id"]
            attempts = attempts_by_txn.get(txn_id, [])

            # We focus on the cohort of transactions that experienced a failure/decision point
            # Either it failed on attempt 1, or it ended in FAILED, or failure_code was logged
            attempt_1 = attempts[0] if attempts else None
            had_failure = (
                (attempt_1 and attempt_1["status"] == "FAILED") or
                row["status"] == "FAILED" or
                bool(row["failure_code"])
            )

            if not had_failure:
                # Immediate clean pass on attempt 1 without recovery need
                continue

            cust_id = row["customer_id"]
            cust = customers_map.get(cust_id, {})
            session = checkout_map.get(txn_id, {})

            # Target: recovered = 1 if final status is SUCCESS, 0 if FAILED
            recovered = 1 if row["status"] == "SUCCESS" else 0

            # Signals strictly available at initial failure (PRE-RECOVERY)
            initial_fail_code = (
                (attempt_1 and attempt_1.get("failure_code")) or
                row.get("failure_code") or
                "UNKNOWN"
            )
            # Use deterministic mapping from failure code so category is leak-free
            from backend.app.failure_classifier import FailureClassifier
            classification = FailureClassifier.classify(initial_fail_code)
            initial_fail_code = classification.failure_code
            initial_fail_category = classification.category.value


            # Parse timestamps
            try:
                txn_created_dt = datetime.fromisoformat(row["created_at"])
                hour = txn_created_dt.hour
            except Exception:
                hour = 12

            try:
                if session and session.get("created_at"):
                    session_created_dt = datetime.fromisoformat(session["created_at"])
                    duration = max(5.0, (txn_created_dt - session_created_dt).total_seconds())
                else:
                    duration = 120.0
            except Exception:
                duration = 120.0

            device_type = infer_device_type(row["payment_method"], cust_id)

            features = {
                "amount": float(row["amount"]),
                "payment_method": row["payment_method"],
                "gateway": row["gateway"],
                "failure_category": initial_fail_category,
                "failure_code": initial_fail_code,
                "attempt_number": 1,  # Evaluated at attempt 1 decision point
                "customer_transaction_count": int(cust.get("total_transactions", 0)),
                "customer_success_rate": float(cust.get("success_rate", 0.0)),
                "customer_average_transaction": float(cust.get("average_transaction_amount", 1000.0)),
                "preferred_payment_method": cust.get("preferred_payment_method", "UPI"),
                "risk_score": float(row.get("risk_score", 0.1)),
                "checkout_duration": duration,
                "device_type": device_type,
                "hour": hour,
                "historical_failure_count": int(cust.get("failed_transactions", 0)),
            }

            rows.append(features)
            targets.append(recovered)

    df_features = pd.DataFrame(rows)
    s_target = pd.Series(targets, name="recovered")

    print(f"Extracted {len(df_features)} failure/recovery instances.")
    print(f"Overall recovery rate: {s_target.mean():.4f} ({s_target.sum()} / {len(s_target)})")

    return df_features, s_target


def train_recovery_model(
    data_dir: str = "data/synthetic",
    model_output: str = "models/recovery_model.joblib",
    test_data_output: str = "models/test_data.joblib",
    random_state: int = 42,
) -> Dict[str, Any]:
    """Trains, calibrates, and serializes the XGBoost recovery prediction model."""
    os.makedirs(os.path.dirname(model_output) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(test_data_output) or ".", exist_ok=True)

    X, y = load_and_engineer_features(data_dir)

    # Stratified 70% train, 15% validation, 15% test split
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=random_state
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.17647, stratify=y_train_val, random_state=random_state
    )  # 0.17647 of 0.85 = ~0.15 of total

    print(f"Dataset split:")
    print(f"  Train: {len(X_train)} instances")
    print(f"  Val:   {len(X_val)} instances")
    print(f"  Test:  {len(X_test)} instances")

    # Build preprocessing pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
            (
                "num",
                StandardScaler(),
                NUMERICAL_FEATURES,
            ),
        ]
    )

    print("Fitting preprocessor on training split...")
    X_train_proc = preprocessor.fit_transform(X_train)
    X_val_proc = preprocessor.transform(X_val)
    X_test_proc = preprocessor.transform(X_test)

    # Get feature names after one-hot encoding
    cat_encoder = preprocessor.named_transformers_["cat"]
    encoded_cat_names = list(cat_encoder.get_feature_names_out(CATEGORICAL_FEATURES))
    all_transformed_feature_names = encoded_cat_names + NUMERICAL_FEATURES

    # Initialize and train XGBClassifier
    print("Training XGBClassifier...")
    base_model = XGBClassifier(
        n_estimators=250,
        max_depth=5,
        learning_rate=0.06,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=random_state,
        n_jobs=-1,
    )

    base_model.fit(
        X_train_proc,
        y_train,
        eval_set=[(X_val_proc, y_val)],
        verbose=False,
    )

    # Fit and calibrate model probabilities using 3-fold cross validation
    print("Calibrating model probabilities...")
    calibrated_model = CalibratedClassifierCV(
        estimator=base_model,
        cv=3,
        method="sigmoid",
    )
    calibrated_model.fit(X_train_proc, y_train)


    # Save model artifact bundle
    model_bundle = {
        "preprocessor": preprocessor,
        "calibrated_model": calibrated_model,
        "raw_model": base_model,
        "transformed_feature_names": all_transformed_feature_names,
        "categorical_features": CATEGORICAL_FEATURES,
        "numerical_features": NUMERICAL_FEATURES,
        "all_input_features": ALL_FEATURES,
        "model_version": "1.0.0-xgb",
        "trained_at": datetime.now().isoformat(),
    }

    joblib.dump(model_bundle, model_output)
    print("Model bundle successfully saved to:", model_output)

    # Save test dataset for clean, leak-free evaluation in evaluate.py
    test_data_bundle = {
        "X_test": X_test,
        "y_test": y_test,
        "X_test_proc": X_test_proc,
    }
    joblib.dump(test_data_bundle, test_data_output)
    print("Held-out test dataset saved to:", test_data_output)

    return {
        "model_output": model_output,
        "test_data_output": test_data_output,
        "train_size": len(X_train),
        "val_size": len(X_val),
        "test_size": len(X_test),
        "feature_count": len(all_transformed_feature_names),
    }


def main():
    parser = argparse.ArgumentParser(description="Train XGBoost Recovery Prediction Model")
    parser.add_argument("--data-dir", type=str, default="data/synthetic", help="Path to synthetic dataset")
    parser.add_argument("--model-output", type=str, default="models/recovery_model.joblib", help="Output path for model")
    parser.add_argument("--test-output", type=str, default="models/test_data.joblib", help="Output path for test data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    train_recovery_model(
        data_dir=args.data_dir,
        model_output=args.model_output,
        test_data_output=args.test_output,
        random_state=args.seed,
    )


if __name__ == "__main__":
    main()
