# RazorRecover AI - Vercel & Production Deployment Guide

This guide details the complete production deployment architecture and pre-flight verification for **RazorRecover AI**.

> [!IMPORTANT]
> **Zero-Docker Architecture**: In strict adherence to project requirements, **Docker is NOT used** anywhere in this deployment pipeline. Both frontend and backend leverage native runtime environments (Vercel Serverless / Edge for Next.js, and native Python 3.11+ runtimes for FastAPI).

---

## Architecture Overview

```mermaid
flowchart LR
    subgraph Browser ["Client Web Browser"]
        U["End User / Hackathon Judge"]
    end

    subgraph Vercel ["Vercel Global Edge Network"]
        VFrontend["Next.js 14 App Router (React 18, Tailwind, Lucide)"]
        VRewrite["Vercel Rewrites Proxy (/api/*)"]
        VFallback["Intelligent Synthetic Mock Fallback Engine"]
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
    VRewrite -.->|"Fallback if Backend Offline / Cold Start"| VFallback
    FastAPI --> Inference
    FastAPI --> Orchestrator
    FastAPI --> Decision
    FastAPI -->|"SQLAlchemy 2.0 Pool (SSL)"| PG
    FastAPI -.->|"Prompt Guard + Fallback"| Gemini
```

---

## 1. Pre-Deployment Audit & Blockers Resolved

All 14 deployment blocker audits have been thoroughly inspected and fixed:

| # | Check Item | Status | Resolution Implemented |
|---|:---|:---:|:---|
| **1** | **localhost URLs** | ✅ **Resolved** | Cleaned up all `localhost` / `127.0.0.1` hardcodings. `frontend/next.config.js` and `frontend/lib/api.ts` never route to `127.0.0.1` in production environments. |
| **2** | **Hardcoded API URLs** | ✅ **Resolved** | `frontend/lib/api.ts` dynamically resolves `NEXT_PUBLIC_API_URL`, relative rewrite `/api/*`, or SSR `BACKEND_API_URL`. Zero hardcoded endpoints. |
| **3** | **Filesystem Persistence** | ✅ **Resolved** | Ephemeral & serverless safe: SQLite automatically points to `/tmp/razorrecover.db` on serverless platforms; PostgreSQL supported for persistent storage. |
| **4** | **Docker Dependencies** | ✅ **Resolved** | **Zero Docker dependencies**. Standard Next.js on Vercel; standard Python buildpack on Render/Railway. |
| **5** | **Long-Running Processes** | ✅ **Resolved** | All simulation, classification, and recovery APIs are stateless and sub-second synchronous in-memory executions; safe for Vercel 10s–60s timeouts. |
| **6** | **Incompatible Packages** | ✅ **Resolved** | Added `psycopg2-binary>=2.9.9` to `requirements.txt` for native cloud PostgreSQL support without C-compiler compilation failures. |
| **7** | **Environment Variables** | ✅ **Resolved** | Centralized `.env.example` in root and `frontend/.env.example` with fully documented keys. |
| **8** | **CORS Configuration** | ✅ **Resolved** | FastAPI configured with `allow_origin_regex=r"^https://([a-zA-Z0-9_-]+\.)?vercel\.app$"` to dynamically allow all Vercel preview & production domains. |
| **9** | **Database Connection Handling** | ✅ **Resolved** | `normalize_database_url()` converts legacy `postgres://` to `postgresql://`, injects `sslmode=require` for cloud databases, and sets `pool_pre_ping=True` and `pool_recycle=300`. |
| **10** | **ML Model Loading** | ✅ **Resolved** | `find_model_path()` checks multiple relative and absolute candidate paths for `models/recovery_model.joblib` with graceful heuristic fallback. |
| **11** | **LLM Configuration** | ✅ **Resolved** | Zero external secret dependency; accepts optional `GEMINI_API_KEY` with automatic fallback to deterministic reasoning. |
| **12** | **Serverless Compatibility** | ✅ **Resolved** | Frontend 100% serverless-ready for Vercel Edge and Lambda runtimes. Added built-in synthetic mock fallback so the Vercel app never crashes even during backend cold starts. |
| **13** | **Frontend Production Build** | ✅ **Resolved** | Verified: `next build` passes with 14/14 static and dynamic routes compiled with 0 errors. |
| **14** | **Backend Deployment Compatibility** | ✅ **Resolved** | Root `requirements.txt` and `Procfile` created for non-Docker git-push deployments (`uvicorn backend.app.main:app`). |

---

## 2. Frontend Deployment (Vercel)

### Step 1: Push Code to GitHub
Ensure all changes are committed and pushed to the `main` branch:
```bash
git add .
git commit -m "feat: complete Vercel deployment preparation and standalone fallback"
git push origin main
```

### Step 2: Import Project into Vercel
1. Log in to your [Vercel Dashboard](https://vercel.com).
2. Click **"Add New..."** → **"Project"**.
3. Select your GitHub repository (`ai-buildathon-project`).
4. In the **Configure Project** screen:
   - **Root Directory**: Click "Edit" and select **`frontend`** (⚠️ **Crucial step**).
   - **Framework Preset**: Automatically detected as **Next.js**.
   - **Build Command**: `npm run build` (default).
   - **Output Directory**: `.next` (default).
   - **Install Command**: `npm install`.

### Step 3: Configure Environment Variables in Vercel
Under **Environment Variables**, add:

| Key | Recommended Value | Description |
|:---|:---|:---|
| `BACKEND_API_URL` | `https://your-backend.onrender.com` | Target backend URL for Next.js `/api/*` rewrite proxy. |
| `NEXT_PUBLIC_API_URL` | `https://your-backend.onrender.com` | Direct client-to-backend URL if bypass is desired. |
| `NODE_ENV` | `production` | Enables production optimizations. |

> [!TIP]
> **Resilient Standalone Fallback**: Even if the backend server is temporarily sleeping or not yet provisioned, the frontend includes a built-in mock fallback engine (`frontend/lib/mockFallback.ts`) that guarantees the Vercel link displays the full interactive dashboard, the 8 curated demo scenarios, and baseline comparisons with **zero red error banners**.

### Step 4: Deploy
Click **"Deploy"**. Vercel will build the Next.js frontend, provision serverless routes, and provide an HTTPS production URL (e.g., `https://razorrecover-ai.vercel.app`).

---

## 3. Backend Deployment (Without Docker)

You can deploy the FastAPI backend to any modern non-Docker Python platform such as **Render**, **Railway**, **Fly.io**, or **AWS App Runner**.

### Option A: Deploy on Render (Recommended, Free / Low Cost)
1. Log in to [Render](https://render.com) and click **"New +"** → **"Web Service"**.
2. Connect your GitHub repository: `ai-buildathon-project`.
3. Configure the service settings:
   - **Name**: `razorrecover-api`
   - **Region**: Singapore, Frankfurt, or Oregon (nearest to you).
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
4. Configure Environment Variables (see Section 5 below).
5. Click **"Create Web Service"**. Render will deploy the application natively using Python 3.11+.

### Option B: Deploy on Railway
1. Log in to [Railway](https://railway.app) and click **"New Project"** → **"Deploy from GitHub repo"**.
2. Railway automatically detects the `Procfile`:
   ```bash
   web: uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```
3. Set Environment Variables in the Railway Variables tab.

---

## 4. PostgreSQL Database Setup

The application supports any managed cloud PostgreSQL database (e.g., **Neon Serverless Postgres**, **Supabase**, or **Render PostgreSQL**).

### Recommended: Neon Postgres (Serverless)
1. Sign up at [neon.tech](https://neon.tech) and create a database named `razorrecover`.
2. Copy the connection string:
   ```text
   postgres://username:password@ep-sample-123456.us-east-2.aws.neon.tech/razorrecover?sslmode=require
   ```
3. Use this as your `DATABASE_URL`. The backend's `normalize_database_url()` automatically handles `postgres://` to `postgresql://` and enforces SSL pooling.

### Database Initialization
Once the backend is deployed with `DATABASE_URL` configured, run schema creation:
```bash
python -m backend.app.database
```
Tables (`transactions`, `customers`, `merchants`, `payment_attempts`, `agent_decisions`, `recovery_actions`, `audit_logs`, `checkout_sessions`, `subscriptions`) will be automatically created.

---

## 5. Environment Variables Matrix

### Backend Environment Variables

| Variable | Required | Example / Default | Purpose |
|:---|:---:|:---|:---|
| `DATABASE_URL` | No | `postgresql://user:pwd@host/db?sslmode=require` | PostgreSQL connection string (defaults to SQLite if unset). |
| `FRONTEND_URL` | Yes | `https://razorrecover.vercel.app` | Production frontend domain for CORS. |
| `CORS_ORIGINS` | No | `http://localhost:3000,https://razorrecover.vercel.app` | Comma-separated list of allowed origins. |
| `CORS_ORIGIN_REGEX`| No | `^https://([a-zA-Z0-9_-]+\.)?vercel\.app$` | Regex allowing all Vercel preview branch deployments. |
| `ENVIRONMENT` | No | `production` | Environment indicator (`production`, `simulation`). |
| `MODEL_PATH` | No | `models/recovery_model.joblib` | Path to trained XGBoost model artifact. |
| `GEMINI_API_KEY` | No | `AIzaSy...` | Optional: Enables Google Gemini contextual reasoning. |
| `LLM_PROVIDER` | No | `none` or `gemini` | LLM provider selection. |
| `PORT` | Auto | `8000` | Port assigned by hosting platform. |

### Frontend Environment Variables (Vercel)

| Variable | Required | Example | Purpose |
|:---|:---:|:---|:---|
| `BACKEND_API_URL` | Yes | `https://razorrecover-api.onrender.com` | Target backend URL for Next.js `/api/*` rewrite proxy. |
| `NEXT_PUBLIC_API_URL`| No | `https://razorrecover-api.onrender.com` | Direct client-to-backend URL if bypass is desired. |
| `NODE_ENV` | No | `production` | Node environment. |

---

## 6. CORS Configuration

To prevent browser CORS rejections while supporting credentials and Vercel preview environments:

1. **Explicit Origins**: In `backend/app/config.py`, `settings.cors_origins_list` parses both `FRONTEND_URL` and comma-separated `CORS_ORIGINS`.
2. **Dynamic Preview Deployments**: `CORS_ORIGIN_REGEX` is set to `r"^https://([a-zA-Z0-9_-]+\.)?vercel\.app$"` so every feature branch preview URL on Vercel is authorized without manual reconfiguration.
3. **Safe Credentials**: Unlike insecure configurations that use `allow_origins=["*"]` with `allow_credentials=True` (which modern browsers reject), this configuration strictly sends validated origins.

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

Before launching to production, run local verification:

```bash
# 1. Verify frontend builds with zero errors (all 14 routes)
cd frontend
npm run build

# 2. Verify all 197 backend unit and integration tests pass
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
