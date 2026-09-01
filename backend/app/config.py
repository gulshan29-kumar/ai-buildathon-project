from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "RazorRecover AI"
    environment: str = "simulation"
    simulated_payments: bool = True
    max_retries_per_event: int = 3
    llm_provider: str = "none"


settings = Settings()
