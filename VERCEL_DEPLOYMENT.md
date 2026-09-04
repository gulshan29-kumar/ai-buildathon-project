# RazorRecover AI - Vercel & Production Deployment Guide

This guide details the complete production deployment architecture for **RazorRecover AI**.

> [!IMPORTANT]
> **Zero-Docker Architecture**: In strict adherence to project requirements, **Docker is NOT used** anywhere in this deployment pipeline. Both frontend and backend leverage native runtime environments (Vercel Serverless / Edge for Next.js, and native Python 3.11+ runtimes for FastAPI).

---

## Architecture Overview

```mermaid
flowchart LR
    subgraph Browser ["Client Web Browser"]
        U["End User / Merchant"]
    end

    subgraph Vercel ["Vercel Global Edge Network"]
        VFrontend["Next.js 14 App Router (React 18, Tailwind, Lucide)"]
        VRewrite["Vercel Rewrites Proxy (/api/*)"]
    end

    subgraph BackendHost ["Cloud Backend (Render / Railway / Fly.io)"]
        FastAPI["FastAPI 0.111 Application (Uvicorn)"]
        Inference["XGBoost / Scikit-Learn Inference Engine"]
        Orchestrator["Recovery Orchestrator & Safe Tools"]
        Decision["Deterministic Decision & Policy Engines"]
    end

    subgraph CloudDB ["Managed Cloud PostgreSQL"]
        PG["Neon / Supabase / AWS RDS"]
    end

    subgraph ExternalServices ["External AI Services (Optional)"]
        Gemini["Google Gemini 1.5 Flash API"]
    end

    U -->|"HTTPS"| VFrontend
    VFrontend -->|"Same-origin API calls (/api/...)"| VRewrite
    VRewrite -->|"Encrypted Reverse Proxy"| FastAPI
    U -.->|"Direct HTTPS (optional)"| FastAPI
    FastAPI --> Inference
    FastAPI --> Orchestrator
    FastAPI --> Decision
    FastAPI -->|"SQLAlchemy 2.0 Pool (SSL)"| PG
    FastAPI -.->|"Prompt Guard + Fallback"| Gemini
```

---

## 1. Pre-Deployment Audit & Blockers Resolved

All 14 deployment blocker audits have been conducted and fixed:

| Check Item | Status | Resolution Implemented |
| :--- | :--- | :--- |
| **1. Localhost URLs** | ✅ Resolved | Removed all hardcoded `localhost` / `127.0.0.1` references from frontend build. |
| **2. Hardcoded API URLs** | ✅ Resolved | `frontend/lib/api.ts` dynamically resolves `NEXT_PUBLIC_API_URL`, relative rewrite `/api/*`, or SSR `BACKEND_API_URL`. |
| **3. Filesystem Persistence** | ✅ Resolved | Ephemeral & serverless safe: no file writes during request processing; state persists in PostgreSQL; ML models loaded in-memory read-only. |
| **4. Docker Dependencies** | ✅ Resolved | **Zero Docker dependencies**. Standard Next.js on Vercel; standard Python buildpacks on backend PaaS. |
| **5. Long-Running Processes** | ✅ Resolved | All simulation and recovery APIs are stateless and sub-second synchronous in-memory executions; safe for Vercel 10s–60s timeouts. |
| **6. Incompatible Packages** | ✅ Resolved | Pure JS/TS frontend dependencies (`lucide-react`, `recharts`, `react 18`). Validated on Node 18/20. |
| **7. Environment Variables** | ✅ Resolved | Centralized `.env.example` in root and `frontend/.env.example` with documented keys. |
| **8. CORS Configuration** | ✅ Resolved | FastAPI configured with `allow_origin_regex=r"^https://([a-zA-Z0-9_-]+\.)?vercel\.app$"` to dynamically allow all Vercel preview & production domains with credentials. |
| **9. Database Connection Handling** | ✅ Resolved | Added `normalize_database_url()` to convert legacy `postgres://` to `postgresql://`, configured `pool_pre_ping=True` and `pool_recycle=300`. |
| **10. ML Model Loading** | ✅ Resolved | `find_model_path()` searches multiple candidate paths for `models/recovery_model.joblib` with graceful heuristic fallback. |
| **11. LLM Configuration** | ✅ Resolved | Zero external secret dependency; accepts optional `GEMINI_API_KEY` with automatic fallback to deterministic reasoning. |
| **12. Serverless Compatibility** | ✅ Resolved | Frontend 100% serverless-ready for Vercel edge and lambda runtimes. |
| **13. Frontend Production Build** | ✅ Resolved | Verified: `next build` passes with 13/13 static and dynamic routes compiled without errors. |
| **14. Backend Deployment** | ✅ Resolved | Root `requirements.txt` and `Procfile` created for non-Docker git-push deployments. |

---

## 2. Frontend Deployment (Vercel)

### Step 1: Push Code to GitHub
Ensure your latest changes are pushed to your GitHub repository:
```bash
git add .
git commit -m "Prepare Vercel deployment without Docker"
git push origin main
```

### Step 2: Import Project into Vercel
1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **"Add New..."** → **"Project"**.
3. Select your GitHub repository (`ai-buildathon-project`).
4. In the configuration screen:
   - **Root Directory**: Click "Edit" and set to `frontend`.
   - **Framework Preset**: Automatically detected as `Next.js`.
   - **Build Command**: `npm run build` (or leave default `next build`).
   - **Output Directory**: `.next` (default).
   - **Install Command**: `npm install`.

### Step 3: Configure Environment Variables in Vercel
Under **Environment Variables**, add:

| Key | Recommended Value | Description |
| :--- | :--- | :--- |
| `BACKEND_API_URL` | `https://your-backend.onrender.com` | Primary backend URL used by Next.js rewrites (`/api/*`). |
| `NEXT_PUBLIC_API_URL` | *(Optional)* | Direct client-to-backend URL if skipping Next.js rewrite proxy. |
| `NODE_ENV` | `production` | Enables production optimizations and telemetry silencing. |

### Step 4: Deploy
Click **"Deploy"**. Vercel will build the Next.js frontend, provision serverless routes, and provide an HTTPS production URL (e.g., `https://razorrecover.vercel.app`).

---

## 3. Backend Deployment (Without Docker)

You can deploy the FastAPI backend to any modern non-Docker Python platform such as **Render**, **Railway**, **Fly.io**, or **AWS App Runner**.

### Option A: Deploy on Render (Recommended, Free / Low Cost)
1. Log in to [Render](https://render.com) and click **"New +"** → **"Web Service"**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Name**: `razorrecover-api`
   - **Region**: Select your preferred region (e.g., Singapore, Frankfurt, Oregon).
   - **Branch**: `main`
   - **Root Directory**: *(leave blank for repository root)*
   - **Runtime**: **Python 3**
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
     ```
4. Set Environment Variables (see Section 5 below).
5. Click **"Create Web Service"**. Render will deploy the application natively using Python 3.11+.

### Option B: Deploy on Railway
1. Log in to [Railway](https://railway.app) and click **"New Project"** → **"Deploy from GitHub repo"**.
2. Railway detects the `Procfile`:
   ```bash
   web: uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```
3. Set the Environment Variables in the Railway Variables tab.

---

## 4. PostgreSQL Database Setup

The application supports any cloud PostgreSQL database (e.g., **Neon Serverless Postgres**, **Supabase**, or **Render PostgreSQL**).

### Recommended: Neon Postgres (Serverless)
1. Sign up at [neon.tech](https://neon.tech) and create a database named `razorrecover`.
2. Copy the connection string:
   ```text
   postgres://username:password@ep-sample-123456.us-east-2.aws.neon.tech/razorrecover?sslmode=require
   ```
3. Use this as your `DATABASE_URL`. The backend's `normalize_database_url()` will automatically handle the `postgres://` prefix.

### Database Initialization
Once the backend is deployed with `DATABASE_URL` configured, run schema creation via the entrypoint or shell:
```bash
python -m backend.app.database
```
Tables (`transactions`, `customers`, `merchants`, `payment_attempts`, `agent_decisions`, `recovery_actions`, `audit_logs`, `checkout_sessions`, `subscriptions`) will be automatically created.

---

## 5. Environment Variables Matrix

### Backend Environment Variables

| Variable | Required | Example / Default | Purpose |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | **Yes** | `postgresql+psycopg://user:pwd@host/db?sslmode=require` | PostgreSQL database connection string. |
| `FRONTEND_URL` | **Yes** | `https://razorrecover.vercel.app` | Production frontend domain for CORS. |
| `CORS_ORIGINS` | No | `http://localhost:3000,https://razorrecover.vercel.app` | Comma-separated list of allowed origins. |
| `CORS_ORIGIN_REGEX`| No | `^https://([a-zA-Z0-9_-]+\.)?vercel\.app$` | Regex allowing all Vercel preview branch deployments. |
| `ENVIRONMENT` | No | `production` | Environment indicator (`production`, `staging`, `development`). |
| `MODEL_PATH` | No | `models/recovery_model.joblib` | Path to trained XGBoost model artifact. |
| `GEMINI_API_KEY` | No | `AIzaSy...` | Optional: Enables Google Gemini contextual reasoning. |
| `LLM_PROVIDER` | No | `none` or `gemini` | LLM provider selection. |
| `PORT` | Auto | `8000` | Port assigned by hosting platform. |

### Frontend Environment Variables (Vercel)

| Variable | Required | Example | Purpose |
| :--- | :---: | :--- | :--- |
| `BACKEND_API_URL` | **Yes** | `https://razorrecover-api.onrender.com` | Target backend URL for Next.js `/api/*` rewrite proxy. |
| `NEXT_PUBLIC_API_URL`| No | `https://razorrecover-api.onrender.com` | Direct client-to-backend URL if bypass is desired. |
| `NODE_ENV` | No | `production` | Node environment. |

---

## 6. CORS Configuration

To prevent browser CORS rejections while supporting credentials and Vercel preview environments:

1. **Explicit Origins**: In `backend/app/config.py`, `settings.cors_origins_list` parses both `FRONTEND_URL` and comma-separated `CORS_ORIGINS`.
2. **Dynamic Preview Deployments**: `CORS_ORIGIN_REGEX` is set to `r"^https://([a-zA-Z0-9_-]+\.)?vercel\.app$"` so every feature branch preview URL on Vercel is authorized without manual reconfiguration.
3. **No Wildcard with Credentials**: Unlike insecure configurations that use `allow_origins=["*"]` with `allow_credentials=True` (which modern browsers reject), this configuration strictly sends valid origins.

---

## 7. Model Artifact Deployment

- **Bundle Location**: `models/recovery_model.joblib` (1.95 MB) is committed directly to the git repository.
- **Resolution Strategy**: `find_model_path()` checks:
  1. `MODEL_PATH` environment variable.
  2. Relative path `models/recovery_model.joblib`.
  3. Absolute path relative to `backend/app/ml/inference.py`.
  4. Working directory path.
- **Cold-Start Resilience**: If the model artifact cannot be found or read, `RecoveryPredictor` gracefully falls back to deterministic heuristic recovery scoring without crashing the application.

---

## 8. LLM Configuration & Fallback Safety

- **Zero Hard Dependency**: RazorRecover AI runs 100% deterministically out-of-the-box. An external LLM API key is **never required** for core payment recovery, policy enforcement, or action execution.
- **Optional Gemini Integration**: If `GEMINI_API_KEY` is configured, `RootCauseAgent` enriches root cause explanations with contextual reasoning.
- **Safety Guardrails**:
  - All LLM outputs pass through Pydantic validators (`RootCauseAnalysisResult`).
  - LLMs are strictly forbidden from altering transaction amounts, inventing payment states, or bypassing `PolicyEngine`.
  - On timeout, rate limit, or invalid response, the system falls back seamlessly to deterministic reasoning.

---

## 9. Verification & Pre-Flight Checklist

Before launching to production, verify:

```bash
# 1. Verify frontend builds with zero errors
cd frontend
npm run build

# 2. Verify all backend unit and integration tests pass
cd ..
.venv/Scripts/pytest backend/tests/

# 3. Verify health endpoint locally
curl http://127.0.0.1:8000/api/health
```

Expected health response:
```json
{
  "status": "healthy",
  "app_name": "RazorRecover AI",
  "environment": "production",
  "database": "connected",
  "ml_model": "loaded"
}
```
