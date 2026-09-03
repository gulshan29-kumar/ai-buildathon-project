from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_env_before_test():
    """Ensure clean sandbox state before each test."""
    client.post("/api/demo/reset")


def test_api_health_endpoint():
    """GET /api/health returns system health and exposes no secrets."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "razorrecover-ai-backend"
    assert data["version"] == "1.0.0"
    assert "database" in data
    assert "simulator" in data
    # Ensure no secrets or API keys are present
    assert "secret" not in str(data).lower()
    assert "password" not in str(data).lower()
    assert "api_key" not in str(data).lower()


def test_post_events_and_idempotency_protection():
    """POST /api/events registers payment event and enforces idempotency."""
    payload = {
        "amount": 2500.0,
        "currency": "INR",
        "payment_method": "UPI",
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
        "idempotency_key": "idemp_test_key_101",
    }

    # Initial ingestion
    res1 = client.post("/api/events", json=payload)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["status"] == "FAILED"
    assert data1["idempotency_key"] == "idemp_test_key_101"
    txn_id = data1["transaction_id"]

    # Duplicate ingestion with same idempotency key
    res2 = client.post("/api/events", json=payload)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["transaction_id"] == txn_id
    assert data2["event_id"] == data1["event_id"]


def test_post_events_pydantic_validation_error():
    """POST /api/events with invalid amount triggers structured 422 error."""
    invalid_payload = {
        "amount": -500.0,  # Invalid negative amount
        "payment_method": "UPI",
    }
    response = client.post("/api/events", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "amount" in str(data["detail"]).lower()


def test_get_transactions_list_and_filtering():
    """GET /api/transactions lists and filters transactions."""
    # Ingest two events with different failure codes
    client.post("/api/events", json={"amount": 1000.0, "failure_code": "GATEWAY_TIMEOUT"})
    client.post("/api/events", json={"amount": 3000.0, "failure_code": "CARD_EXPIRED"})

    res_all = client.get("/api/transactions")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert all_data["total"] >= 2
    assert len(all_data["transactions"]) >= 2

    # Filter by failure code
    res_filtered = client.get("/api/transactions?failure_code=CARD_EXPIRED")
    assert res_filtered.status_code == 200
    filtered_data = res_filtered.json()
    assert all(t["failure_code"] == "CARD_EXPIRED" for t in filtered_data["transactions"])


def test_get_single_transaction_and_404():
    """GET /api/transactions/{transaction_id} returns transaction or structured 404."""
    ingest_res = client.post("/api/events", json={"amount": 4200.0, "failure_code": "INSUFFICIENT_FUNDS"})
    txn_id = ingest_res.json()["transaction_id"]

    # Success case
    res_found = client.get(f"/api/transactions/{txn_id}")
    assert res_found.status_code == 200
    data = res_found.json()
    assert data["transaction_id"] == txn_id
    assert data["amount"] == 4200.0

    # Not found case
    res_missing = client.get("/api/transactions/txn_non_existent_9999")
    assert res_missing.status_code == 404
    err = res_missing.json()
    assert err["error"] == "HTTP_ERROR"
    assert "not found" in err["detail"].lower()


def test_recovery_run_and_status_endpoints():
    """POST /api/recovery/run/{id} and GET /api/recovery/{id} execute and track recovery."""
    ingest = client.post("/api/events", json={"amount": 3500.0, "failure_code": "GATEWAY_TIMEOUT", "payment_method": "UPI"})
    txn_id = ingest.json()["transaction_id"]

    # Before run: check recovery status
    status_before = client.get(f"/api/recovery/{txn_id}")
    assert status_before.status_code == 200
    assert status_before.json()["status"] == "NOT_STARTED"

    # Execute recovery run
    run_res = client.post(f"/api/recovery/run/{txn_id}")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["transaction_id"] == txn_id
    assert run_data["monitoring_outcome"] == "RECOVERED"
    assert run_data["selected_action"] == "RETRY_PAYMENT"

    # After run: check recovery status
    status_after = client.get(f"/api/recovery/{txn_id}")
    assert status_after.status_code == 200
    after_data = status_after.json()
    assert after_data["status"] == "RECOVERED"
    assert after_data["latest_run"]["selected_action"] == "RETRY_PAYMENT"


def test_agent_decision_endpoint():
    """GET /api/agent/decision/{transaction_id} returns explainable decision."""
    ingest = client.post("/api/events", json={"amount": 5000.0, "failure_code": "CARD_EXPIRED", "payment_method": "CARD"})
    txn_id = ingest.json()["transaction_id"]

    res = client.get(f"/api/agent/decision/{txn_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["transaction_id"] == txn_id
    assert data["selected_action"] in {"SWITCH_PAYMENT_METHOD", "SEND_RECOVERY_MESSAGE"}
    assert "candidates" in data
    assert len(data["candidates"]) >= 2
    assert "reasoning_summary" in data


def test_audit_timeline_endpoint():
    """GET /api/audit/{transaction_id} returns chronological immutable events."""
    ingest = client.post("/api/events", json={"amount": 2200.0, "failure_code": "GATEWAY_TIMEOUT"})
    txn_id = ingest.json()["transaction_id"]

    # Run recovery to populate timeline
    client.post(f"/api/recovery/run/{txn_id}")

    res = client.get(f"/api/audit/{txn_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["transaction_id"] == txn_id
    assert data["verified_integrity"] is True
    assert data["count"] >= 3
    event_types = [e["event_type"] for e in data["events"]]
    assert "PAYMENT_FAILED" in event_types
    assert "PAYMENT_RECOVERED" in event_types


def test_dashboard_metrics_endpoint():
    """GET /api/dashboard/metrics aggregates recovery statistics."""
    # Seed payments
    ingest1 = client.post("/api/events", json={"amount": 1000.0, "failure_code": "GATEWAY_TIMEOUT"})
    client.post(f"/api/recovery/run/{ingest1.json()['transaction_id']}")

    res = client.get("/api/dashboard/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "total_failed_volume" in data
    assert "total_revenue_recovered" in data
    assert "recovery_rate" in data
    assert "by_failure_category" in data
    assert "ai_uplift_percentage" in data


def test_simulation_run_and_query_endpoints():
    """POST /api/simulation/run and GET /api/simulation/{run_id} batch scenario execution."""
    sim_request = {
        "transaction_count": 10,
        "seed": 123,
    }
    run_res = client.post("/api/simulation/run", json=sim_request)
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["transaction_count"] == 10
    assert data["status"] == "COMPLETED"
    run_id = data["run_id"]

    # Fetch run details
    get_res = client.get(f"/api/simulation/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == run_id
    assert len(get_res.json()["transactions"]) == 10

    # 404 for missing run
    missing_res = client.get("/api/simulation/sim_run_missing_000")
    assert missing_res.status_code == 404


def test_demo_reset_endpoint():
    """POST /api/demo/reset clears all simulator and sandbox records."""
    client.post("/api/events", json={"amount": 8000.0, "failure_code": "GATEWAY_TIMEOUT"})
    assert client.get("/api/transactions").json()["total"] >= 1

    reset_res = client.post("/api/demo/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ok"

    # Transactions list should be reset to empty
    assert client.get("/api/transactions").json()["total"] == 0
