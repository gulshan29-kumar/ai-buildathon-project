from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.simulation_engine import SimulationEngine

client = TestClient(app)


def test_synthetic_transaction_generation():
    engine = SimulationEngine(seed=123)
    txns = engine.generate_synthetic_transactions(count=20, scenario="mixed_failures")
    assert len(txns) == 20

    for t in txns:
        assert "transaction_id" in t
        assert "amount" in t
        assert t["amount"] > 0
        assert "failure_code" in t
        assert "risk_score" in t
        assert 0.0 <= t["risk_score"] <= 1.0
        assert "customer_history" in t
        assert "payment_context" in t
        assert "recoverable" in t


def test_simulation_seed_determinism():
    e1 = SimulationEngine(seed=999)
    txns1 = e1.generate_synthetic_transactions(count=10, scenario="gateway_outage")

    e2 = SimulationEngine(seed=999)
    txns2 = e2.generate_synthetic_transactions(count=10, scenario="gateway_outage")

    for t1, t2 in zip(txns1, txns2):
        assert t1["amount"] == t2["amount"]
        assert t1["failure_code"] == t2["failure_code"]
        assert t1["payment_method"] == t2["payment_method"]
        assert t1["risk_score"] == t2["risk_score"]


def test_baseline_strategy_execution():
    engine = SimulationEngine(seed=42)

    # Test high risk -> unnecessary intervention & blocked
    high_risk_event = {
        "transaction_id": "txn_test_hr",
        "amount": 25000.0,
        "payment_method": "CARD",
        "failure_code": "HIGH_RISK",
        "risk_score": 0.95,
    }
    base_res = engine.run_baseline_strategy(high_risk_event)
    assert base_res["strategy"] == "BASELINE"
    assert base_res["recovered"] is False
    assert base_res["unnecessary_intervention"] is True
    assert base_res["execution_status"] == "BLOCKED_BY_ACQUIRER"

    # Test declined card -> unnecessary intervention (re-attempts dead card)
    card_event = {
        "transaction_id": "txn_test_card",
        "amount": 4500.0,
        "payment_method": "CARD",
        "failure_code": "CARD_DECLINED",
        "risk_score": 0.05,
    }
    base_card = engine.run_baseline_strategy(card_event)
    assert base_card["recovered"] is False
    assert base_card["unnecessary_intervention"] is True
    assert base_card["execution_status"] == "DECLINED_AGAIN"


def test_ai_strategy_execution():
    engine = SimulationEngine(seed=42)

    # Test temporary timeout -> AI should attempt retry and log audit hash
    timeout_event = {
        "transaction_id": "txn_test_timeout",
        "amount": 12500.0,
        "payment_method": "UPI",
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.04,
    }
    ai_res = engine.run_ai_strategy(timeout_event)
    assert ai_res["strategy"] == "RAZORRECOVER_AI"
    assert ai_res["selected_action"] == "RETRY_PAYMENT"
    assert ai_res["root_cause_category"] == "TEMPORARY"
    assert ai_res["policy_outcome"] == "ALLOWED"
    assert ai_res["audit_hash"] != ""
    assert isinstance(ai_res["recovery_time_ms"], float)

    # Test high risk -> AI should escalate and block
    high_risk_event = {
        "transaction_id": "txn_test_hr_ai",
        "amount": 50000.0,
        "payment_method": "CARD",
        "failure_code": "HIGH_RISK",
        "risk_score": 0.94,
    }
    ai_hr = engine.run_ai_strategy(high_risk_event)
    assert ai_hr["selected_action"] == "ESCALATE"
    assert ai_hr["blocked"] is True
    assert ai_hr["escalated"] is True
    assert ai_hr["recovered"] is False
    assert ai_hr["unnecessary_intervention"] is False  # Safely avoided!


def test_full_comparative_simulation_11_metrics():
    engine = SimulationEngine(seed=42)
    result = engine.run_comparison(transaction_count=30, scenario="mixed_failures")

    assert "run_id" in result
    assert result["total_transactions"] == 30
    assert result["failed_transactions"] == 30
    assert result["recoverable_opportunities"] > 0
    assert result["revenue_at_risk"] > 0

    # Verify all 11 metrics in baseline_metrics
    bm = result["baseline_metrics"]
    required_metrics = [
        "total_transactions",
        "failed_transactions",
        "recoverable_opportunities",
        "revenue_at_risk",
        "recovered_revenue",
        "recovery_rate",
        "average_recovery_time_ms",
        "retry_attempts",
        "blocked_actions",
        "escalations",
        "unnecessary_intervention_rate",
    ]
    for m in required_metrics:
        assert m in bm, f"Metric '{m}' missing in baseline_metrics"

    # Verify all 11 metrics in ai_metrics
    am = result["ai_metrics"]
    for m in required_metrics:
        assert m in am, f"Metric '{m}' missing in ai_metrics"

    # Metric bounds and business logic validations
    assert 0.0 <= bm["recovery_rate"] <= 1.0
    assert 0.0 <= am["recovery_rate"] <= 1.0
    assert bm["recovered_revenue"] <= result["revenue_at_risk"]
    assert am["recovered_revenue"] <= result["revenue_at_risk"]

    # AI should outperform Baseline on mixed failures
    assert am["recovery_rate"] > bm["recovery_rate"]
    assert am["recovered_revenue"] > bm["recovered_revenue"]
    assert am["unnecessary_intervention_rate"] < bm["unnecessary_intervention_rate"]

    # Uplift calculations
    uplift = result["uplift"]
    assert uplift["revenue_gain"] > 0
    assert uplift["recovery_rate_diff_pct"] > 0
    assert uplift["intervention_reduction_pct"] >= 0

    # Persistence verification
    loaded = SimulationEngine.load_run(result["run_id"])
    assert loaded is not None
    assert loaded["run_id"] == result["run_id"]
    assert len(loaded["transactions"]) == 30


def test_api_simulation_endpoints():
    # 1. POST /api/simulation/run
    req_payload = {
        "transaction_count": 25,
        "seed": 101,
        "scenario": "mixed_failures",
    }
    res = client.post("/api/simulation/run", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    run_id = data["run_id"]
    assert data["total_transactions"] == 25
    assert data["ai_metrics"] is not None
    assert data["baseline_metrics"] is not None
    assert len(data["transactions"]) == 25

    # 2. GET /api/simulation/runs
    runs_res = client.get("/api/simulation/runs")
    assert runs_res.status_code == 200
    runs_list = runs_res.json()
    assert isinstance(runs_list, list)
    assert any(r["run_id"] == run_id for r in runs_list)

    # 3. GET /api/simulation/{run_id}
    detail_res = client.get(f"/api/simulation/{run_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["run_id"] == run_id
    assert detail_data["total_transactions"] == 25

    # 4. GET /api/simulation/{run_id}/transaction/{txn_id}
    first_txn_id = data["transactions"][0]["transaction_id"]
    txn_res = client.get(f"/api/simulation/{run_id}/transaction/{first_txn_id}")
    assert txn_res.status_code == 200
    txn_data = txn_res.json()
    assert txn_data["transaction_id"] == first_txn_id
    assert "baseline" in txn_data
    assert "ai" in txn_data
    assert "ai_won" in txn_data
