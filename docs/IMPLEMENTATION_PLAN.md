# BrandSentry AI — Round 2 Implementation Plan

> **Hackathon Deadline:** 25 October 2026, 10:00 AM IST  
> **Core Directive:** Prioritize a functional, verifiable, end-to-end deployed product over unnecessary architectural complexity. Execute sequentially and verify each phase with automated tests before advancing.

---

## Phase Roadmap Overview

| Phase | Title | Primary Focus | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Environment & Project Initialization** | Environment audit, directory scaffolding, configs, health API, base UI | **COMPLETED & VERIFIED** |
| **Phase 2** | **Guideline Ingestion & Vector Indexing** | PDF/TXT parsing, semantic chunking, embeddings, ChromaDB indexing | **NEXT UP** |
| **Phase 3** | **Claim Extraction & 3-Way Verdicts** | Copy parsing, hybrid retrieval, LLM-grounded evaluation engine | **QUEUED** |
| **Phase 4** | **Citation Validation & Corrections** | Citation grounding verification, policy rewrite generator | **QUEUED** |
| **Phase 5** | **Frontend Integration & End-to-End Workflow** | Interactive React UI, guideline upload, claim viewer, report drawer | **QUEUED** |
| **Phase 6** | **Testing, Reliability & Evaluation** | E2E test suites, precision/recall benchmarks, error resilience | **QUEUED** |
| **Phase 7** | **Deployment & Public URL** | Cloud hosting (Cloud Run / Render / Vercel), prod env config | **QUEUED** |
| **Phase 8** | **Documentation & Submission Finalization** | Final submission video, pitch deck, README, audit trail | **QUEUED** |

---

## Detailed Phase Breakdown

---

### PHASE 1 — Environment and Project Initialization
* **Objectives**:
  - Audit Windows OS, Python, Node, npm, and Git availability.
  - Establish a clean, maintainable full-stack project structure (`frontend/`, `backend/`, `data/`, `docs/`).
  - Configure `.env.example`, `.gitignore`, `requirements.txt`, `package.json`, and `tsconfig.json`.
  - Create minimal FastAPI `/health` endpoint and React landing page with live health polling.
  - Validate backend unit tests (`pytest`) and frontend production build (`tsc && vite build`).
* **Files Changed/Created**:
  - `backend/app/main.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `backend/.env.example`
  - `backend/tests/test_health.py`, `pytest.ini`
  - `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`
  - `frontend/src/App.tsx`, `frontend/src/components/HealthStatus.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/services/api.ts`, `frontend/src/index.css`
  - `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/FEATURE_CHECKLIST.md`, `README.md`, `.gitignore`
* **Dependencies**:
  - Backend: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `pytest`, `httpx`, `python-multipart`, `python-dotenv`
  - Frontend: `react`, `react-dom`, `lucide-react`, `vite`, `typescript`
* **Acceptance Criteria**:
  - Backend starts via Uvicorn and responds with HTTP 200 on `GET /health`.
  - Frontend builds with zero TypeScript errors.
  - Frontend displays live health status and handles disconnected backend gracefully.
* **Tests Required**:
  - Unit tests verifying `/health` status code, response schema, and root endpoint.
  - Frontend TypeScript compilation and asset bundling check.
* **Risks & Mitigation**:
  - *Risk*: Python 3.14 compatibility with legacy packages.  
    *Mitigation*: Tested Pydantic and FastAPI wheel installation; pre-screened packages before committing.

---

### PHASE 2 — Guideline Upload, Text Extraction, Chunking, Embeddings, and Indexing
* **Objectives**:
  - Implement file upload API (`POST /api/guidelines/upload`) supporting PDF and TXT.
  - Extract text cleanly using PyMuPDF (`fitz`), preserving page numbers, section headers, and metadata.
  - Chunk document into semantic segments (~300–500 tokens) with 50-token overlap, retaining source citations.
  - Generate dense vector embeddings (using local SentenceTransformers or remote embedding provider).
  - Store indexed chunks in persistent ChromaDB collections under `data/chroma/`.
  - Add lexical index (BM25) for high-precision exact keyword/clause lookup.
* **Files Expected to Change**:
  - `backend/app/api/guidelines.py` (New upload and list endpoints)
  - `backend/app/services/ingestion.py` (File validation, local storage)
  - `backend/app/services/chunking.py` (PDF text extraction, section-aware splitting)
  - `backend/app/retrieval/embeddings.py` (Embedding generator interface)
  - `backend/app/retrieval/vector_store.py` (ChromaDB collection management and persistence)
  - `backend/app/schemas/guideline.py` (Pydantic models for chunks and upload responses)
  - `backend/tests/test_ingestion.py`, `backend/tests/test_chunking.py`
* **Dependencies**:
  - `pymupdf` (fitz), `chromadb`, `sentence-transformers` (or API embedding fallback), `rank-bm25`
* **Acceptance Criteria**:
  - User can upload a multi-page PDF brand guideline.
  - Document text is extracted with accurate page numbers.
  - Chunks are stored in ChromaDB and retrievable via similarity query within < 500ms.
* **Tests Required**:
  - Extraction accuracy test on sample PDF and TXT documents.
  - Chunk metadata integrity test (every chunk has `document_id`, `page_number`, `chunk_id`).
  - Vector search retrieval test verifying that known guideline queries return relevant chunks.
* **Risks**:
  - Large PDF memory overhead or complex column layouts. Handled by robust PyMuPDF text block extraction.

---

### PHASE 3 — Claim Extraction, Retrieval, and Evidence-Grounded Verdicts
* **Objectives**:
  - Parse submitted marketing copy into discrete, testable claims.
  - Retrieve top-k relevant guideline passages for each claim using hybrid dense + sparse search.
  - Implement deterministic pre-filter for blacklisted terms and mandatory disclaimers.
  - Implement provider-independent LLM evaluation service with structured JSON output.
  - Classify each claim into one of three strict verdicts: `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`.
  - Ensure zero false approvals: claims lacking corroborating guideline text must default to `INSUFFICIENT_EVIDENCE`.
* **Files Expected to Change**:
  - `backend/app/api/review.py` (Audit endpoint `POST /api/review/analyze`)
  - `backend/app/services/claim_extractor.py` (Copy decomposition)
  - `backend/app/retrieval/hybrid_search.py` (Dense + BM25 retrieval aggregator)
  - `backend/app/review/deterministic.py` (Regex/rule-based rule filter)
  - `backend/app/review/llm_service.py` (Provider-independent LLM client interface)
  - `backend/app/review/evaluator.py` (Evidence-grounded prompt & Pydantic JSON parser)
  - `backend/app/schemas/review.py` (Pydantic schemas for claims, verdicts, and evidence)
  - `backend/tests/test_claim_extraction.py`, `backend/tests/test_evaluator.py`
* **Dependencies**:
  - LLM SDK (e.g. `google-genai` / `openai` / direct HTTP client via `httpx`)
* **Acceptance Criteria**:
  - Given marketing copy, system extracts discrete claims.
  - Each claim receives a validated 3-way verdict with accompanying rationales and guideline evidence.
  - Unsubstantiated claims never receive `SUPPORTED`.
* **Tests Required**:
  - Golden test suite with synthetic claims: 5 supported, 5 contradicted, 5 insufficient evidence.
  - Verification that hallucinated approvals are 0%.
* **Risks**:
  - LLM latency on long copy. Addressed by parallel retrieval and batched claim evaluation.

---

### PHASE 4 — Citation Validation, Semantic Drift Checks, and Suggested Corrections
* **Objectives**:
  - Build automated citation validator to verify that quoted guideline passages exist verbatim in indexed chunks.
  - Implement semantic drift detector comparing submitted claim meaning against guideline intent.
  - Implement correction suggestion generator that provides compliant rewrites for `CONTRADICTED` or `INSUFFICIENT_EVIDENCE` claims.
  - Generate comprehensive, structured compliance report schema.
* **Files Expected to Change**:
  - `backend/app/review/citation_validator.py` (Verbatim excerpt verifier)
  - `backend/app/review/corrections.py` (LLM-guided compliant rewrite generator)
  - `backend/app/schemas/report.py` (Final audit report schema)
  - `backend/tests/test_citation_validator.py`, `backend/tests/test_corrections.py`
* **Dependencies**:
  - Existing Phase 3 backend services and LLM interface.
* **Acceptance Criteria**:
  - Every citation in the review output is checked against source text; invalid citations are flagged.
  - Contradicted claims receive at least one actionable, compliant rewrite suggestion.
* **Tests Required**:
  - Unit test verifying citation checker flags fabricated quotes.
  - Test verifying correction generator outputs text that clears the compliance filter.
* **Risks**:
  - LLM suggestions changing the core marketing proposition. Constrained with low temperature and strict prompting.

---

### PHASE 5 — React Frontend Integration and Complete Review Workflow
* **Objectives**:
  - Connect React frontend to backend ingestion and review APIs.
  - Build Guideline Upload component with drag-and-drop, progress indication, and indexed document list.
  - Build Marketing Copy Editor with sample presets (e.g. "Compliant Ad", "Violating Superlatives Ad", "Unsubstantiated Copy").
  - Build Interactive Audit Dashboard:
    - Overall compliance score gauge.
    - Interactive claim list with color-coded badges (`SUPPORTED` = Green, `CONTRADICTED` = Red, `INSUFFICIENT_EVIDENCE` = Amber).
    - Citation popover showing exact document page and snippet.
    - One-click "Apply Correction" button to update marketing copy in place.
* **Files Expected to Change**:
  - `frontend/src/components/GuidelineUpload.tsx`
  - `frontend/src/components/CopyEditor.tsx`
  - `frontend/src/components/ReviewDashboard.tsx`
  - `frontend/src/components/ClaimCard.tsx`
  - `frontend/src/components/CitationModal.tsx`
  - `frontend/src/services/reviewApi.ts`
  - `frontend/src/App.tsx`
* **Dependencies**:
  - React, Lucide-react (already configured).
* **Acceptance Criteria**:
  - User can upload guideline, paste copy, click "Audit Copy", and view full interactive breakdown.
  - User can click "Apply Correction" and re-audit the updated copy immediately.
* **Tests Required**:
  - Frontend end-to-end user workflow test in browser.
  - Build smoke test (`tsc && vite build`).
* **Risks**:
  - UI lag during multi-claim audits. Mitigated by asynchronous progress bars and optimistic UI loading states.

---

### PHASE 6 — Testing, Reliability, and Evaluation
* **Objectives**:
  - Comprehensive end-to-end integration tests covering the complete pipeline.
  - Test edge cases: empty files, password-protected PDFs, foreign language text, adversarial prompt injection in marketing copy.
  - Evaluation metric calculation: Precision, Recall, and Grounding Fidelity on benchmark guideline dataset.
  - Logging, latency tracing, and structured error responses.
* **Files Expected to Change**:
  - `backend/tests/test_e2e_workflow.py`
  - `backend/tests/test_edge_cases.py`
  - `backend/app/core/logging.py`
  - `docs/EVALUATION_REPORT.md`
* **Dependencies**:
  - `pytest`, `pytest-asyncio`
* **Acceptance Criteria**:
  - 100% of critical paths covered by automated integration tests.
  - All synthetic adversarial inputs handled gracefully without 500 server crashes.
* **Tests Required**:
  - Full pytest test suite execution.
* **Risks**:
  - Test flakiness due to external LLM calls. Addressed with recorded VCR/fixture runs for deterministic CI tests.

---

### PHASE 7 — Deployment and Public Project URL
* **Objectives**:
  - Containerize backend and frontend (or configure static frontend + cloud backend).
  - Deploy backend to production container host (Cloud Run / Render).
  - Deploy frontend to CDN host (Vercel / Cloudflare Pages / Cloud Run).
  - Configure production environment variables and verify public HTTPS endpoint.
* **Files Expected to Change**:
  - `Dockerfile.backend`, `Dockerfile.frontend`
  - `render.yaml` or `cloudbuild.yaml`
  - Production `.env` configurations
* **Dependencies**:
  - Docker, Cloud platform CLI
* **Acceptance Criteria**:
  - Publicly accessible live URL reachable by judges without local installation.
  - Live demo operates end-to-end against sample guidelines.
* **Tests Required**:
  - Remote health check and sample audit over public HTTPS.
* **Risks**:
  - Cloud cold-starts or storage persistence across restarts. Addressed by lightweight containers and pre-warmed embeddings.

---

### PHASE 8 — Updated Round 2 Documentation and Submission
* **Objectives**:
  - Create final Round 2 submission documentation and summary report.
  - Prepare 3-minute video walk-through demonstrating the live working product.
  - Update repository `README.md` with judge quick-start instructions, architecture diagrams, and live demo links.
  - Final submission checklist review ahead of the 25 Oct 2026 10:00 AM IST deadline.
* **Files Expected to Change**:
  - `README.md`
  - `docs/ROUND2_FINAL_REPORT.md`
  - `docs/FEATURE_CHECKLIST.md` (All P0 items marked TESTED)
* **Acceptance Criteria**:
  - Submission repository is clean, documented, and fully ready for judge evaluation.
