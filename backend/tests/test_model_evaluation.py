import json
import os
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from ml_training.evaluate import compute_metrics, evaluate_model, extract_feature_importances
from ml_training.experiment_tracker import ExperimentTracker


def test_compute_metrics_accuracy_and_bounds():
    y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    y_prob = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1])
    metrics = compute_metrics(y_true, y_prob, threshold=0.5)

    assert metrics["sample_count"] == 8
    assert metrics["recovered_count"] == 4
    assert metrics["recovery_rate"] == 0.5
    assert metrics["roc_auc"] == 1.0
    assert metrics["pr_auc"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["brier_score"] < 0.1

    cm = metrics["confusion_matrix"]
    assert cm["true_positives"] == 4
    assert cm["true_negatives"] == 4
    assert cm["false_positives"] == 0
    assert cm["false_negatives"] == 0
    assert cm["true_positives"] + cm["true_negatives"] + cm["false_positives"] + cm["false_negatives"] == 8


def test_evaluate_model_outputs_genuine_metrics():
    model_path = "models/recovery_model.joblib"
    test_data_path = "models/test_data.joblib"

    if not os.path.exists(model_path) or not os.path.exists(test_data_path):
        pytest.skip("Model bundles not found in models/ directory.")

    report = evaluate_model(
        model_path=model_path,
        test_data_path=test_data_path,
        report_output="ml_training/test_eval_output.json",
        track_experiment=False,
    )

    # Ensure required metadata exists
    assert report["model_version"] == "1.0.0-xgb"
    assert "trained_at" in report
    assert "evaluated_at" in report
    assert "dataset_metadata" in report

    meta = report["dataset_metadata"]
    assert meta["test_samples"] == 4690
    assert meta["raw_features_count"] == 15
    assert meta["encoded_features_count"] == 45
    assert "failure_code" in meta["all_input_features"]
    assert "risk_score" in meta["all_input_features"]

    # Overall metrics bounds
    summary = report["evaluation_summary"]
    metrics = summary["overall_metrics"]
    assert metrics["sample_count"] == 4690
    assert 0.85 <= metrics["roc_auc"] <= 1.0
    assert 0.85 <= metrics["pr_auc"] <= 1.0
    assert 0.80 <= metrics["precision"] <= 1.0
    assert 0.85 <= metrics["recall"] <= 1.0
    assert 0.80 <= metrics["f1"] <= 1.0
    assert 0.0 <= metrics["brier_score"] <= 0.15

    # Check 10-bin calibration curve
    calib = metrics["calibration_curve"]
    assert len(calib) == 10
    for b in calib:
        assert 0.0 <= b["mean_pred"] <= 1.0
        assert 0.0 <= b["actual_pos"] <= 1.0

    # Feature importances
    fi = report["feature_importance"]
    assert len(fi["grouped_features"]) == 15
    top_feature = fi["grouped_features"][0]
    assert top_feature["importance"] > 0.10
    assert top_feature["feature"] in ["failure_code", "failure_category"]

    # Category metrics
    per_cat = report["per_category_metrics"]
    assert "TEMPORARY" in per_cat
    assert "AUTHENTICATION" in per_cat
    assert per_cat["TEMPORARY"]["sample_count"] > 1000

    # Clean up test output
    if os.path.exists("ml_training/test_eval_output.json"):
        os.remove("ml_training/test_eval_output.json")


def test_experiment_tracker_logging():
    tracker = ExperimentTracker(filepath="ml_training/test_experiments.json")
    run = tracker.log_run(
        model_version="1.0.0-xgb-test",
        model_name="XGBoost Calibrated Test",
        hyperparameters={"n_estimators": 100},
        dataset_metadata={"test_samples": 100},
        metrics={"roc_auc": 0.95, "f1": 0.90},
        feature_importance=[{"feature": "risk_score", "importance": 0.5}],
        category_metrics={"TEMPORARY": {"f1": 0.92}},
    )

    assert run["model_version"] == "1.0.0-xgb-test"
    assert run["metrics"]["roc_auc"] == 0.95
    assert len(tracker.load_experiments()) >= 1

    latest = tracker.get_latest_run()
    assert latest["run_id"] == run["run_id"]

    retrieved = tracker.get_run(run["run_id"])
    assert retrieved is not None
    assert retrieved["run_id"] == run["run_id"]

    if os.path.exists("ml_training/test_experiments.json"):
        os.remove("ml_training/test_experiments.json")


def test_api_model_performance_endpoint():
    client = TestClient(app)
    response = client.get("/api/model/performance")
    assert response.status_code == 200
    data = response.json()

    assert "model_version" in data
    assert "evaluation_summary" in data
    metrics = data["evaluation_summary"]["overall_metrics"]
    assert metrics["roc_auc"] is not None
    assert metrics["pr_auc"] is not None
    assert metrics["f1"] is not None
    assert "feature_importance" in data
    assert "per_category_metrics" in data


def test_api_model_evaluate_endpoint():
    client = TestClient(app)
    response = client.post("/api/model/evaluate")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert "report" in data
    assert data["report"]["model_version"] == "1.0.0-xgb"
    assert data["report"]["evaluation_summary"]["overall_metrics"]["roc_auc"] > 0.90
