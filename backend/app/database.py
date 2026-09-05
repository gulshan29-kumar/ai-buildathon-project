from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings


class Base(DeclarativeBase):
    pass


import os


def normalize_database_url(url: str | None) -> str:
    """Normalize database connection URLs for SQLAlchemy and cloud providers (Neon, Supabase, Railway)."""
    if not url:
        # On serverless or read-only container filesystems, use /tmp or in-memory
        if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("SERVERLESS"):
            return "sqlite:////tmp/razorrecover.db"
        return "sqlite:///./razorrecover.db"
    clean_url = url.strip()
    # Cloud providers often supply postgres:// instead of postgresql://
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql://", 1)
    return clean_url


def get_engine(url: str | None = None):
    db_url = normalize_database_url(url or settings.DATABASE_URL)
    connect_args: dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 15}
        return create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    try:
        # PostgreSQL with cloud pooling configuration
        # For remote cloud databases (Neon, Supabase, Railway), enable SSL if not specified
        if "sslmode" not in db_url and "localhost" not in db_url and "127.0.0.1" not in db_url:
            connect_args["sslmode"] = "require"
        return create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=10,
            max_overflow=20,
            connect_args=connect_args,
        )
    except (ImportError, ModuleNotFoundError, Exception):
        fallback_url = (
            "sqlite:////tmp/razorrecover.db"
            if (os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
            else "sqlite:///./razorrecover.db"
        )
        return create_engine(
            fallback_url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False, "timeout": 15},
        )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    from backend.app.models import (  # noqa: F401
        AgentDecision,
        AuditLog,
        CheckoutSession,
        Customer,
        Merchant,
        PaymentAttempt,
        RecoveryAction,
        RecoveryResult,
        SimulationRun,
        Subscription,
        Transaction,
    )

    bind_engine = target_engine or engine
    Base.metadata.create_all(bind=bind_engine)


def create_db_if_missing(target_engine=None) -> None:
    """Initialize tables in development or test environments."""
    init_db(target_engine=target_engine)


if __name__ == "__main__":
    init_db()
    print("Database schema initialized successfully.")

