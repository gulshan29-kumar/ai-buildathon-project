import os
from typing import List, Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    APP_NAME: str = "RazorRecover AI"
    ENVIRONMENT: str = "simulation"
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/razorrecover",
        )
    )
    FRONTEND_URL: str = Field(
        default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:3000")
    )
    CORS_ORIGINS: str = Field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,https://razorrecover.vercel.app",
        )
    )
    CORS_ORIGIN_REGEX: str = Field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGIN_REGEX",
            r"^https://([a-zA-Z0-9_-]+\.)?vercel\.app$",
        )
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    MODEL_PATH: str = Field(
        default_factory=lambda: os.getenv("MODEL_PATH", "models/recovery_model.joblib")
    )
    simulated_payments: bool = True
    max_retries_per_event: int = 3
    llm_provider: str = "none"

    @property
    def app_name(self) -> str:
        return self.APP_NAME

    @property
    def environment(self) -> str:
        return self.ENVIRONMENT

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def frontend_url(self) -> str:
        return self.FRONTEND_URL

    @property
    def cors_origins_list(self) -> List[str]:
        origins = set()
        if self.FRONTEND_URL:
            origins.add(self.FRONTEND_URL.rstrip("/"))
        for o in self.CORS_ORIGINS.split(","):
            cleaned = o.strip().rstrip("/")
            if cleaned:
                origins.add(cleaned)
        return list(origins)


settings = Settings()


