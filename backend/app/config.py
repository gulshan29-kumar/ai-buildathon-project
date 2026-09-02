import os
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


settings = Settings()

