import pytest
from fastapi.testclient import TestClient

from backend.app.baseline_comparison import BaselineComparisonEngine, STRATEGY_NAMES
from backend.app.main import app


def test_fixed_test_dataset_determinism():
    engine = BaselineComparisonEngine(seed=42)
    events_1 = engine.generate_fixed_test_dataset(count=50, seed=42)
    events_2 = engine.generate_fixed_test_dataset(count=50, seed=42)

    assert len(events_1) == 50
    assert len(events_2) == 50

    for i in range(50):
        assert events_1[i]["transaction_id"] == events_2[i]["transaction_id"]
        assert events_1[i]["amount"] == events_2[i]["amount"]
        assert events_1[i]["failure_code"] == events_2[i]["failure_code"]
        assert events_1[i]["risk_score"] == events_2[i]["risk_score"]


def test_six_strategies_execution_and_metrics():
    engine = BaselineComparisonEngine(seed=42)
    res = engine.run_benchmark(transaction_count=50, scenario="mixed_failures", seed=42, save_results=False)

    assert res["total_transactions"] == 50
    assert res["revenue_at_risk"] > 0
    strats = res["strategies"]

    # Verify all 6 strategies exist
    for s_name in STRATEGY_NAMES:
        assert s_name in strats
        m = strats[s_name]
        # Check all 10 metrics are present and non-negative
        assert "revenue_recovered" in m
        assert "recovery_rate" in m
        assert "revenue_at_risk" in m
        assert "additional_revenue" in m
        assert "average_recovery_time_ms" in m
        assert "retry_count" in m
        assert "false_intervention_rate" in m
        assert "unnecessary_retry_rate" in m
        assert "escalation_rate" in m
        assert "blocked_unsafe_actions" in m

    # 1. No Recovery baseline checks
    no_rec = strats["NO_RECOVERY"]
    assert no_rec["revenue_recovered"] == 0.0
    assert no_rec["recovery_rate"] == 0.0
    assert no_rec["retry_count"] == 0

    # 2. Fixed Retry Rule checks
    fixed = strats["FIXED_RETRY_RULE"]
    assert fixed["retry_count"] == 50  # Blindly retried all 50
    assert fixed["blocked_unsafe_actions"] == 0
    assert fixed["unnecessary_retry_rate"] > 0

    # 3. ML-only checks
    ml_only = strats["ML_ONLY"]
    assert ml_only["recovery_rate"] >= fixed["recovery_rate"]

    # 4. ML + Decision Engine checks
    dec_eng = strats["ML_DECISION_ENGINE"]
    assert dec_eng["revenue_recovered"] > ml_only["revenue_recovered"]
    assert dec_eng["recovery_rate"] > ml_only["recovery_rate"]

    # 5. ML + Agent checks
    agent = strats["ML_AGENT"]
    assert agent["revenue_recovered"] >= dec_eng["revenue_recovered"] * 0.95

    # 6. ML + Agent + Guardrails checks
    guardrails = strats["ML_AGENT_GUARDRAILS"]
    assert guardrails["recovery_rate"] >= fixed["recovery_rate"]
    assert guardrails["revenue_recovered"] > fixed["revenue_recovered"]
    # Crucial safety check: Guardrails must intercept and block unsafe actions
    assert guardrails["blocked_unsafe_actions"] > 0
    assert guardrails["unnecessary_retry_rate"] == 0.0


def test_benchmark_metrics_arithmetic_consistency():
    engine = BaselineComparisonEngine(seed=123)
    res = engine.run_benchmark(transaction_count=30, seed=123, save_results=False)

    risk = res["revenue_at_risk"]
    for s_name, data in res["strategies"].items():
        assert data["revenue_at_risk"] == risk
        assert data["total_transactions"] == 30
        assert 0.0 <= data["recovery_rate"] <= 100.0
        assert 0.0 <= data["false_intervention_rate"] <= 100.0
        assert 0.0 <= data["unnecessary_retry_rate"] <= 100.0
        assert 0.0 <= data["escalation_rate"] <= 100.0
        # Additional revenue check
        no_rec_rev = res["strategies"]["NO_RECOVERY"]["revenue_recovered"]
        assert round(data["additional_revenue"], 2) == round(data["revenue_recovered"] - no_rec_rev, 2)


def test_api_benchmark_endpoints():
    client = TestClient(app)

    # 1. Run benchmark POST
    payload = {
        "transaction_count": 25,
        "seed": 99,
        "scenario": "mixed_failures",
        "save_results": True,
    }
    response = client.post("/api/benchmark/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "benchmark_id" in data
    assert data["total_transactions"] == 25
    assert len(data["strategies"]) == 6
    assert "ML_AGENT_GUARDRAILS" in data["strategies"]

    # 2. Get latest benchmark GET
    res_latest = client.get("/api/benchmark/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.json()
    assert latest_data["benchmark_id"] == data["benchmark_id"]

    # 3. History endpoint GET
    res_history = client.get("/api/benchmark/history")
    assert res_history.status_code == 200
    history_data = res_history.json()
    assert isinstance(history_data, list)
    assert len(history_data) >= 1
