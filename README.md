# BrandSentry AI — Brand Compliance Intelligence Platform

[![Live App](https://img.shields.io/badge/Live%20Demo-brandsentry--web.onrender.com-blue?style=for-the-badge&logo=render)](https://brandsentry-web.onrender.com)
[![API Docs](https://img.shields.io/badge/API%20Docs-FastAPI%20Swagger-009688?style=for-the-badge&logo=fastapi)](https://brandsentry-api.onrender.com/docs)
[![Health Check](https://img.shields.io/badge/Backend-%2Fhealth-10B981?style=for-the-badge)](https://brandsentry-api.onrender.com/health)
[![Backend Tests](https://img.shields.io/badge/Backend%20Tests-270%20Passed-success?style=for-the-badge&logo=pytest)](docs/FINAL_SUBMISSION_REPORT.md)
[![Frontend Tests](https://img.shields.io/badge/Frontend%20Tests-15%20Passed-success?style=for-the-badge&logo=vitest)](docs/TEST_REPORT.md)

---

## Overview

BrandSentry AI is an **AI-powered, evidence-grounded, human-in-the-loop compliance review assistant**. Upload regulatory or brand guideline documents (PDF/TXT), paste marketing copy (or an image for OCR), and BrandSentry extracts each claim, retrieves matching guideline passages, and returns a `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE` verdict with verbatim citations, an explanation, and — where safe — a draft correction marked for human review.

It is a review aid, not an autonomous approver: verdicts are only as good as the uploaded guidelines and measured accuracy is well below 100% (see *Known Limitations* below).

### Core capabilities
- Per-claim extraction with negation/disclaimer handling and prompt-injection boundaries
- Hybrid retrieval: ChromaDB dense (`all-MiniLM-L6-v2`) + BM25, fused with Reciprocal Rank Fusion (k=60); optional cross-encoder reranking
- Deterministic, evidence-grounded verdicts (`verdict == compliance_verdict`), citations validated against retrieved text, document/policy-version scoping
- Universal risk warnings (e.g. absolute claims) kept separate from organization-specific violations
- Conservative `INSUFFICIENT_EVIDENCE` when guidelines do not address a claim
- Policy versioning, persistent review audit trail, JSON/CSV/PDF export, image OCR review

---

## 🌐 Live Production Deployment

BrandSentry AI is deployed in production on Render:

| Service | Public Endpoint URL | Purpose / Notes |
| :--- | :--- | :--- |
| **Frontend Web Application** | [https://brandsentry-web.onrender.com](https://brandsentry-web.onrender.com) | Interactive React + Vite compliance workspace |
| **Backend REST API** | [https://brandsentry-api.onrender.com](https://brandsentry-api.onrender.com) | FastAPI backend serving hybrid retrieval, review & audit |
| **API Interactive Documentation** | [https://brandsentry-api.onrender.com/docs](https://brandsentry-api.onrender.com/docs) | Interactive OpenAPI / Swagger UI test interface |
| **Backend Health Check** | [https://brandsentry-api.onrender.com/health](https://brandsentry-api.onrender.com/health) | Live service status (`status: "ok"`, uptime, version) |

*Hosted on Render's free tier: the API sleeps when idle (first request can take ~45s) and storage is ephemeral, so re-upload guidelines after a restart. Full details: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).*

---

## 🚀 Round 3 Committed Improvements

### 1. Hybrid Retrieval & Measurable Evaluation
- **Sparse Lexical Search (BM25Okapi)**: Tokenized keyword inverted index indexing identical guideline passages, preserving chunk IDs, document IDs, source filenames, and page numbers with JSON persistence.
- **Reciprocal Rank Fusion (RRF)**: Fuses dense semantic search (`all-MiniLM-L6-v2` via ChromaDB) with BM25 lexical scores using the formula $RRF(d) = \sum \frac{1}{k + rank(d)}$ ($k=60$), combined with string deduplication to eliminate redundant evidence citations.
- **Empirical Evaluation Benchmark**: 60 meticulously labelled ground-truth scenarios across 10 failure categories (Exact Phrase, Semantic Paraphrase, Numerical Thresholds, Prohibited Phrases, Exceptions, Negation, Temporal, Scope, Missing Evidence, Similar Passages).
  - **Verdict accuracy (Stage 3.5, measured)**: development set 96.67% hybrid (58/60, the set used during tuning); independent holdout 78.81% hybrid / 80.51% dense (N=118); blind challenge set 75.00% hybrid / 71.88% dense (N=32).
  - **Latency**: Hybrid yields ~5ms retrieval on standard CPU infrastructure.
  - Complete report: [`docs/RETRIEVAL_EVALUATION.md`](docs/RETRIEVAL_EVALUATION.md).

### 2. Policy Governance & Auditable Reviews
- **Immutable Policy Versioning**: Added `policy_versions` table in SQLite (`data/documents.db`) with unique version UUIDs, stable policy IDs, human-readable labels (`v1.0`, `v2.0`...), and cryptographic SHA-256 hashes. Multiple versions of the same policy coexist without destructive overwrites.
- **Persistent Review Auditing**: Dedicated SQLite store (`data/reviews.db`) recording review session UUID, source (`text` or `image`), exact policy version IDs used, aggregate counts, and complete JSON claims array with quotes, page numbers, and drift results.
- **Multi-Format Report Export**: One-click direct downloads for official compliance records:
  - **JSON**: Machine-readable audit payload.
  - **CSV**: Tabular breakdown of claim-by-claim verdicts, quotes, and suggested corrections.
  - **PDF**: Professional styled multi-page PDF generated via ReportLab with executive summary, metadata badges, verdict tables, evidence citations, and legal disclaimers.

### 3. Multimodal Visual Brand Compliance
- **OCR Service**: Integrates Tesseract OCR and Pillow image validation supporting PNG, JPEG, and WebP promotional creatives up to 10MB and 8000px dimensions.
- **Traceable Text Extraction**: Preprocessing via grayscale and autocontrast, word-level confidence scoring ($0.0 - 100.0\%$), and bounding boxes.
- **Human-in-the-Loop Review**: Marketers inspect extracted OCR text, view confidence metrics, and edit/correct typographical misrecognitions directly in the UI before compliance review.
- **Pipeline Reuse**: User-verified copy is evaluated through the exact same claim extraction, hybrid retrieval, and evidence-grounded verdict engine, with audit records marked as `review_source="image"`.

---

## 🔄 Technical Architecture

```mermaid
flowchart TD
    subgraph Client ["Frontend (React 18 + TypeScript + Vite)"]
        UI_Dash["Dashboard (Live Analytics & Stats)"]
        UI_Review["Review Workspace (Text & Image OCR Tabs)"]
        UI_Gov["Policy Library & Version History"]
        UI_Audit["Audit Trail & Report Export Center"]
    end

    subgraph API ["FastAPI ASGI Backend"]
        R_Health["/health"]
        R_Guide["/api/guidelines (Upload, Search, Versions)"]
        R_Review["/api/review (Text, Image OCR, Image Submit)"]
        R_Audit["/api/reviews (History, Stats, PDF/CSV/JSON Export)"]
    end

    subgraph Engines ["Core Processing Engines"]
        OCR["OCR Service (Tesseract + Pillow)"]
        ClaimExt["Deterministic Claim Extractor"]
        Hybrid["Hybrid Retriever (Dense ChromaDB + BM25Okapi via RRF)"]
        Verdict["Verdict Engine (SUPPORTED / CONTRADICTED / INSUFFICIENT)"]
        Drift["Semantic Drift & Exaggeration Detector"]
    end

    subgraph Persistence ["Persistent Storage Layer"]
        DB_Docs[("data/documents.db (SQLite Registry & Versions)")]
        DB_Reviews[("data/reviews.db (SQLite Audit History)")]
        Vol_Chroma[("data/chroma/ (ChromaDB Vector Store)")]
        Vol_BM25[("data/bm25/bm25_chunks.json (BM25 Chunks)")]
    end

    UI_Review -->|Upload Graphic| R_Review
    R_Review --> OCR --> UI_Review
    UI_Review -->|Submit Text / Image Copy| R_Review
    R_Review --> ClaimExt --> Hybrid
    Hybrid --> Verdict --> Drift --> DB_Reviews
    DB_Docs --> R_Guide
    DB_Reviews --> R_Audit
    R_Audit -->|PDF / CSV / JSON Download| UI_Audit
```

---

## 🛠️ Technology Stack

### Backend Stack
* **Language & Runtime**: Python 3.11 in the production Docker image; local test suite run on 3.14.5
* **API Framework**: FastAPI 0.115+ with Pydantic v2 schemas
* **Server**: Uvicorn ASGI
* **Vector Store**: ChromaDB with persistent on-disk storage
* **Dense Embeddings**: `all-MiniLM-L6-v2` via ONNX Runtime CPU inference (384 dimensions)
* **Lexical Retrieval**: `rank-bm25` (BM25Okapi)
* **Document Extraction**: PyMuPDF 2.0 (`fitz`)
* **OCR Engine**: Tesseract OCR + `pytesseract` + Pillow (PIL)
* **PDF Report Generation**: ReportLab
* **Metadata & Auditing**: SQLite (`data/documents.db`, `data/reviews.db`)

### Frontend Stack
* **Framework**: React 18.3 with TypeScript
* **Build Tool**: Vite 6
* **Icons**: Lucide React
* **Styling**: Vanilla CSS design system with curated HSL color tokens, dark mode accents, responsive grid, and accessible contrast

---

## 💻 Local Setup & Development

### Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: v20 or higher
* **Git**
* **Tesseract OCR** (Optional for local OCR execution; backend container includes Tesseract automatically):
  - Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`
  - Windows: Install from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

### 1. Clone & Setup
```bash
git clone https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI.git
cd BRAND_SENTRY_AI
```

### 2. Backend Setup
```bash
# Create and activate virtual environment
python -m venv backend/venv
source backend/venv/bin/activate  # On Windows: .\backend\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Run backend development server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
* Backend API: `http://127.0.0.1:8000`
* Swagger Documentation: `http://127.0.0.1:8000/docs`
* Health Check: `http://127.0.0.1:8000/health`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
* Open `http://localhost:5173` in your browser.

---

### 4. Demo walkthrough
1. Open the frontend and wait for the backend status indicator to show connected.
2. **Guidelines** → upload `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt` (indexes as 3 chunks).
3. **Claim Review** → paste `Our product is 100% safe for everyone. Our office is open on weekdays.` → **Review Compliance**.
4. Expected: claim 1 `CONTRADICTED`, citing *"Marketing materials must not describe a product as “100% safe”."* with a draft correction marked for human review; claim 2 `INSUFFICIENT_EVIDENCE` (the guideline does not cover office hours).
5. **Audit History** → export the review as JSON, CSV, or PDF.

---

## 🧪 Automated Testing & Verification

### Run Backend Test Suite (270 Tests Passing)
```bash
python -m pytest -q
```
Covers:
- Hybrid retrieval, BM25 indexing, and RRF fusion (`test_hybrid_retrieval.py`)
- Policy versioning, review audit persistence, and PDF/CSV exports (`test_policy_governance.py`)
- Image validation, format checks, and OCR extraction (`test_ocr_multimodal.py`)
- Review pipeline, input validation, and scoping regression (`test_review_api.py`)
- Verdict engine, deterministic rules, and evidence grounding (`test_verdict_engine.py`)
- Semantic drift categories and uncertainty guardrails (`test_semantic_drift.py`)
- ChromaDB vector store, distance metrics, and embeddings (`test_vector_store.py`)

### Run Frontend Test Suite (15 Tests Passing)
```bash
cd frontend
npm test
```

### Run Frontend Production Build
```bash
cd frontend
npm run build
```

### Run Retrieval Evaluation Benchmark
```bash
python backend/evaluation/evaluate_retrieval.py
```

---

## ⚠️ Known Limitations & Deployment Notes

1. **Free-Tier Render Ephemeral Storage**:
   The deployed backend runs on Render's free web service tier. On the free tier, the container spins down after 15 minutes of inactivity. When it restarts, the local filesystem resets to the clean base Docker container image. In production, attach a persistent disk volume mounted at `/app/backend/data/` or configure S3 / Cloud Storage connectors.
2. **Free-Tier Cold Starts**:
   When spinning up from standby, the initial cold start can take 30–50 seconds to initialize the ASGI container and load embedding models into memory. The frontend includes non-blocking connection indicators and bounded retry logic.
3. **Pure CPU Inference**:
   The ONNX embedding model and BM25 index run entirely on CPU without GPU acceleration, providing maximum deployment portability without recurring GPU costs.
4. **Compliance reasoning is not perfect**:
   Holdout accuracy is ~79–81%. Known failure modes: false-positive contradictions in some operational contexts, conditional-approval/policy-nuance cases, documentary-evidence edge cases, and conservative `INSUFFICIENT_EVIDENCE` when the relevant rule sits in a long multi-topic chunk (e.g. "customer data is completely secure" against the bundled sample guideline). Every verdict needs human review before publication.
5. **Small evaluation corpus**: benchmarks are 60 / 118 / 32 cases; results may not generalize to other guideline sets.
6. **Mobile layout**: the workspace is usable but overflows horizontally on phone-width screens.
7. **No authentication or rate limiting** on the public API.

---

## 📄 Documentation Sitemap

- [System Architecture Specification](docs/ARCHITECTURE.md)
- [Implementation Summary (Round 3 Improvements)](docs/IMPLEMENTATION_SUMMARY.md)
- [Retrieval Benchmark & Measured Evaluation Report](docs/RETRIEVAL_EVALUATION.md)
- [Feature Implementation & Verification Checklist](docs/FEATURE_CHECKLIST.md)
- [Testing & Quality Assurance Report](docs/TEST_REPORT.md)
- [Product & Engineering Roadmap](docs/ROADMAP.md)
- [Hybrid Retrieval Architecture](docs/HYBRID_RETRIEVAL_ARCHITECTURE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Final Submission Report](docs/FINAL_SUBMISSION_REPORT.md)

---

## 🏆 Submission Information
**Team:** We Code Coders  
**Competition:** Round 3: The Final Round  
**Repository:** [https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI.git](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI.git)  
**Branch:** `main` (development history preserved on `round-3-final`)
