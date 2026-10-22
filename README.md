# BrandSentry AI — Brand Compliance & Claim Verification Platform

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-6.1-646CFF.svg)](https://vitejs.dev/)
[![Status](https://img.shields.io/badge/Phase%201-Verified-10B981.svg)]()

> **Hackathon Deadline:** 25 October 2026, 10:00 AM IST  
> **Round 2 Objective:** Deliver an evidence-grounded, verifiable brand compliance platform that reviews marketing copy against uploaded brand guidelines with zero hallucinated approvals.

---

## 1. Project Overview

Marketing and advertising teams face immense compliance, legal, and reputational risks when releasing content that contradicts official brand guidelines, violates trademark standards, or makes unsubstantiated product claims. Manual review is slow and error-prone, while generic LLMs often hallucinate approvals when no explicit rule is retrieved.

**BrandSentry AI** solves this with an evidence-grounded review pipeline:
1. **Guideline Ingestion**: Upload brand guideline rulebooks (PDF/TXT).
2. **Semantic & Lexical Indexing**: Chunk documents with page-level citations and index into ChromaDB & BM25.
3. **Claim Extraction**: Decompose marketing copy into atomic, verifiable claims.
4. **Three-Way Verdict Engine**:
   - `SUPPORTED`: Claim directly substantiated by guideline evidence with verifiable citations.
   - `CONTRADICTED`: Claim violates or exceeds guideline restrictions.
   - `INSUFFICIENT_EVIDENCE`: No matching guideline passage found. **Never approved automatically**.
5. **Verifiable Citations & Suggested Corrections**: Direct excerpts and policy-compliant rewrite suggestions.

---

## 2. Full-Stack Project Structure

```
hackthon/
├── frontend/                     # React 18 + TypeScript + Vite Client
│   ├── src/
│   │   ├── components/           # UI Components (Header, HealthStatus, etc.)
│   │   ├── pages/                # Page Views
│   │   ├── services/             # API client & health check callers
│   │   ├── types/                # TypeScript interfaces
│   │   ├── hooks/                # Custom React hooks
│   │   ├── App.tsx               # Primary application component
│   │   ├── main.tsx              # React DOM entry point
│   │   └── index.css             # Dark-mode design system & animations
│   ├── public/                   # Static assets
│   ├── package.json              # NPM dependencies & scripts
│   ├── tsconfig.json             # TypeScript compiler settings
│   └── vite.config.ts            # Vite bundler & reverse proxy config
│
├── backend/                      # FastAPI Python ASGI Application
│   ├── app/
│   │   ├── api/                  # API routers (guidelines, review, etc.)
│   │   ├── core/                 # Settings, configuration, logging
│   │   ├── models/               # Domain & database models
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── services/             # Ingestion, parsing, chunking services
│   │   ├── retrieval/            # Vector embeddings & ChromaDB store
│   │   ├── review/               # Evaluation engine & deterministic rules
│   │   └── main.py               # FastAPI entry point & CORS
│   ├── tests/                    # Pytest test suite
│   ├── requirements.txt          # Python dependencies
│   └── .env.example              # Environment variables template
│
├── data/                         # Persistent runtime storage (git-ignored)
│   ├── uploads/                  # Uploaded PDF/TXT guidelines
│   └── chroma/                   # Persistent vector database collections
│
├── docs/                         # Engineering & Architecture Documentation
│   ├── ARCHITECTURE.md           # 14-component architectural specification
│   ├── IMPLEMENTATION_PLAN.md    # 8-phase milestone roadmap
│   └── FEATURE_CHECKLIST.md      # P0, P1, P2 feature tracking
│
├── documents/                    # Round 1 proposals and reference submissions
├── .gitignore                    # Version control ignore rules
├── pytest.ini                    # Pytest configuration
└── README.md                     # Project README & local setup guide
```

---

## 3. Local Development Quickstart

### Prerequisites
* **Operating System**: Windows / macOS / Linux
* **Python**: 3.12+ (tested and verified on Python 3.14.5)
* **Node.js**: v20+ (tested on Node v24.16.0)
* **NPM**: v10+ (tested on npm 11.13.0)

---

### Step A: Backend Setup

1. **Navigate to the backend directory and activate the virtual environment**:
   ```powershell
   # Windows PowerShell (from repository root)
   python -m venv backend/venv
   .\backend\venv\Scripts\Activate.ps1
   ```

2. **Install dependencies**:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

3. **Configure environment variables**:
   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```

4. **Run backend test suite**:
   ```powershell
   .\backend\venv\Scripts\pytest -v
   ```

5. **Start the FastAPI backend server**:
   ```powershell
   .\backend\venv\Scripts\uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   * The API will be live at: `http://127.0.0.1:8000`
   * Interactive Swagger docs at: `http://127.0.0.1:8000/docs`
   * Health endpoint: `http://127.0.0.1:8000/health`

---

### Step B: Frontend Setup

1. **Navigate to the frontend directory**:
   ```powershell
   cd frontend
   ```

2. **Install npm dependencies**:
   ```powershell
   npm install
   ```

3. **Run TypeScript compilation & production build check**:
   ```powershell
   npm run build
   ```

4. **Start the local development server**:
   ```powershell
   npm run dev
   ```
   * Open `http://localhost:5173` in your browser.
   * The landing page automatically connects to `http://127.0.0.1:8000/health` and displays the live service status.

---

## 4. Phase 1 Verification Summary

* **FastAPI Backend**: Verified via `pytest` (3/3 passing in 0.66s). Live HTTP GET `/health` returns `{ "status": "ok", "service": "BrandSentry AI", "version": "0.1.0", "environment": "development" }`.
* **React Frontend**: Verified via `tsc && vite build` (zero errors, bundle size ~161 kB JS, ~5.5 kB CSS).
* **Architecture & Planning**: Completed in `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/FEATURE_CHECKLIST.md`.

---

## 5. Security & Isolation

* Secrets and API keys are strictly excluded from source code and managed via `.env` files.
* Vector storage and uploaded files reside in `data/chroma/` and `data/uploads/`, both ignored by version control.
* CORS headers are strictly constrained to local development ports.
