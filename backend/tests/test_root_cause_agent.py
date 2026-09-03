from __future__ import annotations

import json
import pytest

from backend.app.root_cause_agent import (
    RootCauseAgent,
    RootCauseAnalysisResult,
)


@pytest.fixture
def agent():
    return RootCauseAgent()


def test_deterministic_classification_known_codes(agent):
    """Known failure codes must use deterministic classification."""
    # 1. Gateway Timeout
    res_timeout = agent.analyze(
        transaction={"transaction_id": "txn_001", "amount": 2500.0, "payment_method": "UPI"},
        failure_code="GATEWAY_TIMEOUT",
    )
    assert isinstance(res_timeout, RootCauseAnalysisResult)
    assert res_timeout.category == "TEMPORARY"
    assert res_timeout.temporary is True
    assert res_timeout.recoverability == "HIGH"
    assert res_timeout.confidence >= 0.90
    assert "transient" in res_timeout.explanation.lower() or "timeout" in res_timeout.explanation.lower()

    # 2. Expired Card
    res_card = agent.analyze(
        transaction={"transaction_id": "txn_002", "amount": 1500.0, "payment_method": "CARD"},
        failure_code="CARD_EXPIRED",
    )
    assert res_card.category == "PAYMENT_METHOD"
    assert res_card.temporary is False
    assert res_card.recoverability in {"LOW", "NONE"}

    # 3. Insufficient Funds
    res_funds = agent.analyze(
        transaction={"transaction_id": "txn_003", "amount": 4500.0, "payment_method": "NETBANKING"},
        failure_code="INSUFFICIENT_FUNDS",
    )
    assert res_funds.category == "CUSTOMER"
    assert res_funds.temporary is False
    assert res_funds.recoverability == "LOW"

    # 4. High Risk
    res_risk = agent.analyze(
        transaction={"transaction_id": "txn_004", "amount": 10000.0, "risk_score": 0.95},
        failure_code="HIGH_RISK",
    )
    assert res_risk.category == "RISK"
    assert res_risk.temporary is False
    assert res_risk.recoverability in {"LOW", "NONE"}


def test_llm_contextual_explanation_enrichment():
    """Valid LLM reasoning and explanation is accepted and validated via Pydantic."""
    def mock_valid_llm(prompt: str) -> str:
        return json.dumps({
            "category": "TEMPORARY",
            "reason": "Gateway latency burst during bank peak hour reconciliation.",
            "temporary": True,
            "recoverability": "HIGH",
            "confidence": 0.96,
            "explanation": "Transaction failed because the acquiring bank experienced a temporary latency burst. Customer has a 95% historical success rate and payment can be safely recovered.",
        })

    agent_llm = RootCauseAgent(llm_client=mock_valid_llm)
    res = agent_llm.analyze(
        transaction={"transaction_id": "txn_mock_1", "amount": 1200.0, "payment_method": "UPI"},
        failure_code="GATEWAY_TIMEOUT",
        customer_context={"customer_id": "cust_vip_1", "success_rate": 0.95},
    )

    assert isinstance(res, RootCauseAnalysisResult)
    assert res.category == "TEMPORARY"
    assert res.temporary is True
    assert res.deterministic_fallback_used is False
    assert "latency burst" in res.explanation.lower()


def test_llm_hallucination_successful_payment_rejected():
    """LLM must NOT invent that a failed payment succeeded."""
    def hallucinating_llm(prompt: str) -> str:
        return json.dumps({
            "category": "TEMPORARY",
            "reason": "Payment succeeded.",
            "temporary": False,
            "recoverability": "NONE",
            "confidence": 0.99,
            "explanation": "The payment was successful and money has already been captured into the account.",
        })

    agent_hallucinate = RootCauseAgent(llm_client=hallucinating_llm)
    res = agent_hallucinate.analyze(
        transaction={"transaction_id": "txn_fail_1", "amount": 2000.0, "status": "FAILED"},
        failure_code="GATEWAY_TIMEOUT",
    )

    # Hallucination guardrail must trigger deterministic fallback
    assert res.deterministic_fallback_used is True
    assert "payment was successful" not in res.explanation.lower()
    assert res.category == "TEMPORARY"


def test_llm_hallucination_invented_amount_rejected():
    """LLM must NOT invent or change transaction amounts."""
    def amount_altering_llm(prompt: str) -> str:
        return json.dumps({
            "category": "TEMPORARY",
            "reason": "Amount issue.",
            "temporary": True,
            "recoverability": "HIGH",
            "confidence": 0.95,
            "explanation": "Transaction of ₹99,999.00 failed due to gateway timeout.",
        })

    agent_amount = RootCauseAgent(llm_client=amount_altering_llm)
    res = agent_amount.analyze(
        transaction={"transaction_id": "txn_amt_1", "amount": 1000.0, "status": "FAILED"},
        failure_code="GATEWAY_TIMEOUT",
    )

    # Rejection of invented ₹99,999 amount when actual amount is ₹1,000
    assert res.deterministic_fallback_used is True
    assert "₹99,999" not in res.explanation
    assert "₹1,000.00" in res.explanation


def test_llm_failure_uses_deterministic_fallback():
    """If LLM client throws an exception, use deterministic fallback."""
    def broken_llm(prompt: str) -> str:
        raise ConnectionError("LLM API endpoint connection reset by peer")

    agent_broken = RootCauseAgent(llm_client=broken_llm)
    res = agent_broken.analyze(
        transaction={"transaction_id": "txn_err_1", "amount": 3500.0},
        failure_code="BANK_UNAVAILABLE",
    )

    assert isinstance(res, RootCauseAnalysisResult)
    assert res.deterministic_fallback_used is True
    assert res.category == "BANK"
    assert res.temporary is True


def test_malformed_llm_response_uses_fallback():
    """If LLM returns invalid JSON or gibberish, use deterministic fallback."""
    def malformed_llm(prompt: str) -> str:
        return "I think the failure was due to some server issue but I cannot output JSON <<ERR>>"

    agent_malformed = RootCauseAgent(llm_client=malformed_llm)
    res = agent_malformed.analyze(
        transaction={"transaction_id": "txn_mal_1", "amount": 5000.0},
        failure_code="GATEWAY_TIMEOUT",
    )

    assert isinstance(res, RootCauseAnalysisResult)
    assert res.deterministic_fallback_used is True
    assert res.category == "TEMPORARY"


def test_pydantic_schema_validation(agent):
    """Ensure all required fields are strictly validated with Pydantic."""
    res = agent.analyze(
        transaction={"amount": 800.0},
        failure_code="CUSTOMER_ABANDONED",
    )

    data = res.to_dict()
    assert "category" in data
    assert "reason" in data
    assert "temporary" in data
    assert "recoverability" in data
    assert "confidence" in data
    assert "explanation" in data

    # Re-validate with Pydantic model
    validated = RootCauseAnalysisResult.model_validate(data)
    assert validated.category == res.category
    assert validated.temporary == res.temporary


def test_missing_context_resilience(agent):
    """Missing or empty inputs should return safe fallback without crashing."""
    res = agent.analyze(
        transaction={},
        failure_code=None,
        customer_context=None,
        payment_context=None,
    )
    assert isinstance(res, RootCauseAnalysisResult)
    assert res.category is not None
    assert res.confidence >= 0.0
