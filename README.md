# RazorRecover AI

Autonomous Revenue Recovery for Failed Payments and Abandoned Checkouts

## Overview

RazorRecover AI is a fintech AI hackathon project that combines:
- synthetic payment event generation
- ML-based recoverability prediction
- deterministic safety policies
- an LLM-powered decision layer
- a payment simulation engine
- a revenue monitoring dashboard

This project is designed to demonstrate how AI can detect revenue loss, explain likely root causes, and select safe recovery actions without touching real payment infrastructure.

## Scope and Constraints

This project intentionally uses synthetic data only.

- No private production database access
- No private Razorpay internal systems
- No live payment execution
- No real money processing
- No Docker dependency
- Frontend deployable to Vercel
- Simulation-first architecture

## Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- Recharts

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy

### Data and ML
- pandas
- scikit-learn
- XGBoost

### Agentic Layer
- LangGraph
- configurable LLM provider
- deterministic fallback

### Testing
- pytest
- frontend type checking and tests

## Repository Structure

```text
razorrecover-ai/
├── frontend/
├── backend/
├── data/
├── ml/
├── docs/
├── ARCHITECTURE.md
├── README.md
├── .gitignore
└── .env.example
```

## Project Goals

- detect revenue risk from failed payments and abandonments
- classify failure root cause
- predict recoverability and expected value
- apply deterministic policy checks before any action executes
- simulate recovery actions safely
- compare AI-driven decisions against baseline behavior
- provide transparent audit logs and revenue dashboards

## Architecture

The system design is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## Planned Workflow

1. Synthetic event generation
2. Event ingestion and normalization
3. Context retrieval
4. Failure classification
5. ML scoring
6. Policy validation
7. Agentic decision
8. Payment simulation
9. Outcome monitoring
10. Audit + dashboard reporting

## Deployment Notes

- Frontend target: Vercel
- Backend target: managed Python hosting without Docker
- Database target: PostgreSQL-compatible managed database
- Simulation layer: deterministic local execution for demo and evaluation

## Development Status

This repository is currently in the architecture and planning phase.

Planned implementation phases:
- foundation and schema design
- synthetic data generation
- ML models and evaluation
- policy and simulator engine
- LangGraph orchestration
- frontend dashboards and demo flows
- production-style validation and polish

## Setup (placeholder)

```bash
# frontend
cd frontend
npm install
npm run dev

# backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Notes

The project is intentionally simulation-based. Payment execution is not real, and the architecture is designed so that a real payment provider or webhook integration could be introduced later behind the same contracts and safety layer.
