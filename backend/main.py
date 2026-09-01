from fastapi import FastAPI

app = FastAPI(title="RazorRecover AI API", version="0.1.0")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "razorrecover-ai-backend"}


@app.get("/")
def root():
    return {
        "project": "RazorRecover AI",
        "tagline": "Autonomous Revenue Recovery for Failed Payments and Abandoned Checkouts",
        "mode": "simulation-only",
    }
