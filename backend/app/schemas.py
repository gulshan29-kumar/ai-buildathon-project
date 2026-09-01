from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CustomerContext(BaseModel):
    customer_id: str
    risk_score: float = Field(ge=0, le=1)
    preferred_payment_method: str = "CARD"
    historical_declines: int = 0
    churn_likelihood: float = Field(ge=0, le=1)


class PaymentContext(BaseModel):
    order_id: str
    merchant_id: str
    amount: float
    currency: str = "INR"
    payment_method: str = "CARD"
    attempt_count: int = 0
    status: str = "FAILED"
    metadata: Dict[str, Any] = {}


class RecoveryDecision(BaseModel):
    event_id: str
    recommended_action: str
    reasoning: str
    expected_recovery_value: float
    policy_passed: bool = True
    next_action: Optional[str] = None
    audit_trail: List[str] = []
