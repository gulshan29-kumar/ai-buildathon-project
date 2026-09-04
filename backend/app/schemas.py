from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CustomerContext(BaseModel):
    customer_id: str
    risk_score: float = Field(ge=0, le=1)
    preferred_payment_method: str = "CARD"
    historical_declines: int = 0
    churn_likelihood: float = Field(default=0.0, ge=0, le=1)


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


class EventIngestRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Payment transaction amount in INR")
    currency: str = Field(default="INR", description="Currency ISO code")
    payment_method: str = Field(default="UPI", description="Payment method instrument")
    gateway: str = Field(default="SIMULATOR", description="Gateway/Acquirer rail")
    customer_id: str = Field(default="cust_demo", description="Customer identifier")
    merchant_id: str = Field(default="merch_demo", description="Merchant identifier")
    failure_code: Optional[str] = Field(default=None, description="Specific failure code")
    risk_score: float = Field(default=0.05, ge=0.0, le=1.0, description="Fraud risk score")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key")
    transaction_id: Optional[str] = Field(default=None, description="Optional custom transaction ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata payload")


class EventIngestResponse(BaseModel):
    event_id: str
    transaction_id: str
    status: str
    message: str
    idempotency_key: Optional[str] = None
    simulated: bool = True


class TransactionResponse(BaseModel):
    transaction_id: str
    customer_id: str
    merchant_id: str
    amount: float
    currency: str
    payment_method: str
    gateway: str
    status: str
    failure_code: Optional[str] = None
    risk_score: float
    attempt_number: int
    created_at: str
    updated_at: str
    simulated: bool = True


class TransactionListResponse(BaseModel):
    transactions: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class RecoveryRunResponse(BaseModel):
    transaction_id: str
    selected_action: str
    monitoring_outcome: str
    recovery_probability: float
    expected_recovery_value: float
    execution_result: Dict[str, Any]
    policy_decision: Dict[str, Any]
    errors: List[str] = []


class AgentDecisionResponse(BaseModel):
    transaction_id: str
    selected_action: str
    recovery_probability: float
    expected_recovery_value: float
    reasoning_summary: str
    policy_status: str
    candidates: List[Dict[str, Any]]
    fallback_used: bool = False


class DashboardMetricsResponse(BaseModel):
    total_failed_volume: float
    total_failed_count: int
    total_revenue_recovered: float
    total_recovered_count: int
    recovery_rate: float
    active_escalations_count: int
    ai_uplift_percentage: float
    by_failure_category: Dict[str, int]
    by_recovery_action: Dict[str, int]
    revenue_at_risk: Optional[float] = None
    recoverable_revenue: Optional[float] = None
    revenue_recovered: Optional[float] = None
    failed_payments_count: Optional[int] = None
    abandoned_checkouts_count: Optional[int] = None
    active_recoveries_count: Optional[int] = None
    escalations_count: Optional[int] = None
    revenue_over_time: Optional[List[Dict[str, Any]]] = None
    baseline_vs_ai: Optional[Dict[str, Any]] = None
    recovery_probability_distribution: Optional[List[Dict[str, Any]]] = None
    # Phase 17: Checkout Abandonment Metrics
    abandoned_checkout_revenue: Optional[float] = None
    recoverable_abandonment_revenue: Optional[float] = None
    recovered_abandonment_revenue: Optional[float] = None


class CheckoutSessionCreateRequest(BaseModel):
    customer_id: str
    cart_value: float = Field(gt=0, description="Cart monetary value in INR")
    stage: Optional[str] = Field(default="PRODUCT_VIEW", description="Initial lifecycle stage")
    device: Optional[str] = Field(default="MOBILE", description="User device (MOBILE, DESKTOP, TABLET)")
    payment_method: Optional[str] = Field(default="UPI", description="Target payment method")
    previous_purchases: Optional[int] = Field(default=0, ge=0)
    previous_abandonment_count: Optional[int] = Field(default=0, ge=0)
    risk_score: Optional[float] = Field(default=0.05, ge=0.0, le=1.0)
    dnd_enabled: Optional[bool] = Field(default=False, description="Whether customer has DND/opt-out enabled")


class CheckoutEventRequest(BaseModel):
    stage: str = Field(description="New lifecycle stage (PRODUCT_VIEW, CHECKOUT_STARTED, PAYMENT_PAGE_OPENED, PAYMENT_INITIATED, PAYMENT_SUCCESS, ABANDONED)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CheckoutRecoveryRequest(BaseModel):
    force_action: Optional[str] = Field(default=None, description="Optional override action (SEND_RECOVERY_MESSAGE, SCHEDULE_RETRY, STOP)")


class CheckoutRecoveryResponse(BaseModel):
    session_id: str
    cart_value: float
    dropoff_stage: Optional[str] = None
    selected_action: str
    recovery_probability: float
    expected_recovery_value: float
    policy_outcome: str
    policy_rule_id: str
    candidates: List[Dict[str, Any]]
    execution: Dict[str, Any]
    recovered: bool
    recovered_amount: float
    audit_hash: Optional[str] = None
    session: Dict[str, Any]


class SimulationRunRequest(BaseModel):
    transaction_count: int = Field(default=50, ge=1, le=1000, description="Number of transactions to simulate")
    seed: int = Field(default=42, description="Random seed for deterministic reproduction")
    scenario: Optional[str] = Field(default="mixed_failures", description="Simulation scenario type")


class SimulationComparisonMetrics(BaseModel):
    total_transactions: int
    failed_transactions: int
    recoverable_opportunities: int
    revenue_at_risk: float
    recovered_revenue: float
    recovered_count: int
    recovery_rate: float
    average_recovery_time_ms: float
    retry_attempts: int
    blocked_actions: int
    escalations: int
    unnecessary_intervention_rate: float


class SimulationRunResponse(BaseModel):
    run_id: str
    seed: int
    transaction_count: int
    recovered_count: int
    recovered_revenue: float
    recovery_rate: float
    status: str
    created_at: Optional[str] = None
    scenario: Optional[str] = None
    total_transactions: Optional[int] = None
    failed_transactions: Optional[int] = None
    recoverable_opportunities: Optional[int] = None
    revenue_at_risk: Optional[float] = None
    baseline_metrics: Optional[SimulationComparisonMetrics] = None
    ai_metrics: Optional[SimulationComparisonMetrics] = None
    uplift: Optional[Dict[str, Any]] = None
    category_breakdown: Optional[Dict[str, Any]] = None
    ai_actions_distribution: Optional[Dict[str, int]] = None
    transactions: List[Dict[str, Any]] = []


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
    ml_model: str
    policy_engine: str
    simulator: str

