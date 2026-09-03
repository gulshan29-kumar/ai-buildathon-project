from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["project"] == "RazorRecover AI"


def test_api_policies_endpoint():
    response = client.get("/api/policies")
    assert response.status_code == 200
    data = response.json()
    assert "policies" in data
    assert len(data["policies"]) == 12
    rule_ids = [p["rule_id"] for p in data["policies"]]
    assert "POL-001" in rule_ids
    assert "POL-012" in rule_ids


def test_api_classify_endpoint():
    response = client.post("/api/classify", json={"failure_code": "GATEWAY_TIMEOUT"})
    assert response.status_code == 200
    data = response.json()
    assert data["failure_code"] == "GATEWAY_TIMEOUT"
    assert data["category"] == "TEMPORARY"
    assert data["automatic_recovery"] is True


def test_api_decide_endpoint():
    payload = {
        "transaction": {
            "transaction_id": "txn_test_api_1",
            "amount": 2500.0,
            "status": "FAILED",
            "failure_code": "GATEWAY_TIMEOUT",
            "payment_method": "UPI",
            "risk_score": 0.15,
        }
    }
    response = client.post("/api/decide", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == "txn_test_api_1"
    assert data["selected_action"] in {"RETRY_PAYMENT", "SCHEDULE_RETRY"}
    assert data["recovery_probability"] > 0
    assert data["expected_recovery_value"] > 0
    assert len(data["candidates"]) == 6

