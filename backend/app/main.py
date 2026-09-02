from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "razorrecover-ai-backend"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "project": settings.APP_NAME,
        "tagline": "Autonomous Revenue Recovery for Failed Payments and Abandoned Checkouts",
        "mode": "simulation-only",
    }
