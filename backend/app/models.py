from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_transaction_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    preferred_payment_method: Mapped[str] = mapped_column(String(32), default="CARD", nullable=False)
    customer_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="customer")
    checkout_sessions: Mapped[list["CheckoutSession"]] = relationship(back_populates="customer")


    __table_args__ = (
        Index("ix_customers_risk_score", "risk_score"),
        Index("ix_customers_success_rate", "success_rate"),
    )


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="merchant")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="merchant")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    gateway: Mapped[str] = mapped_column(String(64), default="SIMULATOR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="transactions")
    merchant: Mapped[Merchant] = relationship(back_populates="transactions")
    payment_attempts: Mapped[list["PaymentAttempt"]] = relationship(back_populates="transaction")
    checkout_sessions: Mapped[list["CheckoutSession"]] = relationship(back_populates="transaction")
    recovery_actions: Mapped[list["RecoveryAction"]] = relationship(back_populates="transaction")
    recovery_results: Mapped[list["RecoveryResult"]] = relationship(back_populates="transaction")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="transaction")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="transaction")

    __table_args__ = (
        Index("ix_transactions_customer_id", "customer_id"),
        Index("ix_transactions_merchant_id", "merchant_id"),
        Index("ix_transactions_status", "status"),
        Index("ix_transactions_failure_code", "failure_code"),
        Index("ix_transactions_risk_score", "risk_score"),
        Index("ix_transactions_created_at", "created_at"),
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    gateway: Mapped[str] = mapped_column(String(64), default="SIMULATOR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="FAILED", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="payment_attempts")

    __table_args__ = (
        Index("ix_payment_attempts_transaction_id", "transaction_id"),
        Index("ix_payment_attempts_status", "status"),
        UniqueConstraint("transaction_id", "attempt_number", name="uq_payment_attempt_transaction_attempt"),
    )


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.customer_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ABANDONED", nullable=False)
    abandonment_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped[Transaction | None] = relationship(back_populates="checkout_sessions")
    customer: Mapped[Customer | None] = relationship(back_populates="checkout_sessions")


    __table_args__ = (
        Index("ix_checkout_sessions_status", "status"),
        Index("ix_checkout_sessions_customer_id", "customer_id"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    renewal_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="subscriptions")
    merchant: Mapped[Merchant] = relationship(back_populates="subscriptions")

    __table_args__ = (
        Index("ix_subscriptions_customer_id", "customer_id"),
        Index("ix_subscriptions_status", "status"),
    )


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    predicted_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_recovery_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    policy_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="recovery_actions")
    recovery_result: Mapped["RecoveryResult | None"] = relationship(back_populates="recovery_action")

    __table_args__ = (
        Index("ix_recovery_actions_transaction_id", "transaction_id"),
        Index("ix_recovery_actions_action_type", "action_type"),
    )


class RecoveryResult(Base):
    __tablename__ = "recovery_results"

    result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=False)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_actions.action_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    recovered_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    success_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="recovery_results")
    recovery_action: Mapped[RecoveryAction | None] = relationship(back_populates="recovery_result")

    __table_args__ = (
        Index("ix_recovery_results_transaction_id", "transaction_id"),
        Index("ix_recovery_results_status", "status"),
    )


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=False)
    selected_action: Mapped[str] = mapped_column(String(64), nullable=False)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="agent_decisions")

    __table_args__ = (
        Index("ix_agent_decisions_transaction_id", "transaction_id"),
        Index("ix_agent_decisions_selected_action", "selected_action"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_transaction_id", "transaction_id"),
        Index("ix_audit_logs_event_type", "event_type"),
    )

    def __init__(self, **kwargs: Any) -> None:
        if "metadata" in kwargs and "event_metadata" not in kwargs:
            kwargs["event_metadata"] = kwargs.pop("metadata")
        super().__init__(**kwargs)



class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    baseline_revenue_recovered: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_revenue_recovered: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    revenue_at_risk: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recoverable_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recovery_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_simulation_runs_seed", "seed"),
        Index("ix_simulation_runs_created_at", "created_at"),
    )
