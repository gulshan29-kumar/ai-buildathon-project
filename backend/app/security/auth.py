from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from backend.app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Configurable master API keys
DEFAULT_SIMULATION_KEY = "rr_live_sim_key_2026"


def get_authorized_keys() -> set[str]:
    """Retrieves allowed API keys from environment or defaults."""
    env_keys = os.getenv("AUTHORIZED_API_KEYS", "")
    keys = {k.strip() for k in env_keys.split(",") if k.strip()}
    keys.add(DEFAULT_SIMULATION_KEY)
    return keys


def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None),
) -> str:
    """FastAPI dependency for verifying API authorization.
    
    Accepts:
    1. Header `X-API-Key: <key>`
    2. Header `Authorization: Bearer <key>`
    
    In simulation/dev environments with API_AUTH_ENFORCED=False, allows open requests
    unless an invalid key is explicitly supplied.
    """
    enforced = os.getenv("API_AUTH_ENFORCED", "false").lower() in ("true", "1", "yes")

    token = x_api_key
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    valid_keys = get_authorized_keys()

    if not token:
        if enforced:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API authentication credentials. Provide 'X-API-Key' or 'Authorization: Bearer' header.",
            )
        return "anonymous_simulation_client"

    # Constant-time comparison against valid keys
    is_valid = any(secrets.compare_digest(token, k) for k in valid_keys)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key or authorization token provided.",
        )

    return token
