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


def test_api_predict_actions_endpoint():
    payload = {
        "transaction": {
            "transaction_id": "txn_pred_1",
            "amount": 5000.0,
            "failure_code": "GATEWAY_TIMEOUT",
            "risk_score": 0.05,
        }
    }
    response = client.post("/api/predict/actions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == "txn_pred_1"
    assert data["amount"] == 5000.0
    assert len(data["predictions"]) == 6
    action_dict = {p["action"]: p for p in data["predictions"]}
    assert "RETRY_PAYMENT" in action_dict
    assert action_dict["RETRY_PAYMENT"]["probability"] >= 0.75
    assert action_dict["RETRY_PAYMENT"]["expected_recovery_value"] == round(5000.0 * action_dict["RETRY_PAYMENT"]["probability"], 2)


def test_api_predict_single_action_endpoint():
    payload = {
        "transaction": {
            "amount": 3000.0,
            "failure_code": "CARD_EXPIRED",
        },
        "action": "SWITCH_PAYMENT_METHOD",
    }
    response = client.post("/api/predict/action", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "SWITCH_PAYMENT_METHOD"
    assert data["probability"] >= 0.70
    assert data["expected_recovery_value"] == round(3000.0 * data["probability"], 2)


def test_api_orchestrate_endpoint():
    payload = {
        "transaction_id": "txn_api_orch_1",
        "amount": 3500.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "payment_method": "UPI",
        "risk_score": 0.05,
    }
    response = client.post("/api/orchestrate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == "txn_api_orch_1"
    assert data["monitoring_outcome"] == "RECOVERED"
    assert data["selected_action"] == "RETRY_PAYMENT"
    assert "execution_result" in data



