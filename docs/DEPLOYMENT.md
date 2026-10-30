# BrandSentry AI — Deployment Guide

This guide describes how BrandSentry AI is actually deployed, based on the configuration files in this
repository (`render.yaml`, `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`,
`backend/app/core/config.py`, `frontend/src/services/api.ts`). Facts that were observed against the live
services are marked **Verified**; everything else is configuration guidance.

---

## A. Architecture

```
 Browser ──HTTPS──▶ brandsentry-web (Render static site, Vite build of frontend/)
    │
    └──HTTPS (fetch, CORS)──▶ brandsentry-api (Render web service, Docker: Dockerfile.backend)
                                 │  FastAPI + Uvicorn (Python 3.11)
                                 ├─ Claim extractor (deterministic)
                                 ├─ Hybrid retriever: ChromaDB dense + BM25 → RRF (k=60)
                                 │     optional cross-encoder rerank (off by default)
                                 ├─ Verdict engine (deterministic rules + evidence grounding,
                                 │     optional LLM path only when LLM_API_KEY is configured)
                                 └─ $DATA_DIR  (/app/backend/data in the container)
                                       ├─ uploads/        original guideline files
                                       ├─ chroma/         ChromaDB persistent vector store
                                       ├─ bm25/           BM25 chunk index (JSON)
                                       ├─ documents.db    SQLite document + policy-version registry
                                       └─ reviews.db      SQLite review audit trail
```

| Component | Implementation |
| :--- | :--- |
| Frontend hosting | Render **static site** `brandsentry-web` (`runtime: static`), SPA rewrite `/* → /index.html` |
| Backend hosting | Render **web service** `brandsentry-api` (`runtime: docker`, `plan: free`, region `oregon`) |
| API communication | Browser calls the API directly over HTTPS; base URL from `VITE_API_BASE_URL` at build time |
| Vector store | ChromaDB `PersistentClient` at `$DATA_DIR/chroma`, collection `guideline_chunks` |
| Embedding model | `all-MiniLM-L6-v2` (384-dim) via ChromaDB's ONNX `DefaultEmbeddingFunction`; Sentence-Transformers fallback. Pre-downloaded into the Docker image at build time |
| Reranker (optional) | `Xenova/ms-marco-MiniLM-L-6-v2` (ONNX). Only used when `RETRIEVAL_MODE=hybrid_rerank`; downloaded lazily from Hugging Face on first use; falls back to RRF order on failure |
| Document storage | Container filesystem under `$DATA_DIR` (see section F) |
| AI workflow | upload → extract (PyMuPDF / text) → chunk → embed → index (Chroma + BM25) → review: extract claims → retrieve per claim → verdict + citations + safe correction → persist audit |

---

## B. Environment variables

Backend (read by `backend/app/core/config.py` via pydantic-settings; `.env` is git-ignored):

| Variable | Required | Description | Example placeholder |
| :--- | :---: | :--- | :--- |
| `APP_ENV` | no | Environment label shown by `/health` | `production` |
| `DEBUG` | no | Debug flag | `false` |
| `PORT` | no | Port Uvicorn binds to (Render injects it) | `8000` |
| `ALLOWED_ORIGINS` | **yes (prod)** | Comma-separated CORS origins | `https://your-frontend.example.com` |
| `DATA_DIR` | no | Root for uploads, Chroma, BM25, SQLite | `/app/backend/data` |
| `UPLOADS_DIR`, `CHROMA_PERSIST_DIR`, `BM25_PERSIST_DIR`, `DOCUMENTS_DB_PATH`, `REVIEWS_DB_PATH` | no | Override individual paths (default: under `DATA_DIR`) | `/data/chroma` |
| `RETRIEVAL_MODE` | no | `hybrid` (default), `hybrid_rerank`, `dense`, `bm25` | `hybrid` |
| `RRF_SMOOTHING_K` | no | RRF constant | `60` |
| `RERANKER_MODEL_NAME` | no | Cross-encoder repo id (only for `hybrid_rerank`) | `Xenova/ms-marco-MiniLM-L-6-v2` |
| `VERDICT_SIMILARITY_THRESHOLD` | no | Approximate cosine floor for evidence candidates. **Not** a calibrated confidence | `0.25` |
| `LLM_PROVIDER`, `LLM_MODEL` | no | Optional LLM path | `gemini`, `gemini-1.5-flash` |
| `LLM_API_KEY` | no (secret) | Enables the optional LLM path. Set only in the hosting dashboard; never commit | `<set-in-dashboard>` |

Frontend (Vite, inlined at **build** time):

| Variable | Description | Example |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Public backend URL, no trailing slash | `https://your-api.example.com` |

If `VITE_API_BASE_URL` is unset, `frontend/src/services/api.ts` falls back to
`https://brandsentry-api.onrender.com` when served from `*.onrender.com`, otherwise `http://127.0.0.1:8000`.

---

## C. Backend deployment

| Item | Value |
| :--- | :--- |
| Runtime | Docker (`Dockerfile.backend`), base image `python:3.11-slim` + `tesseract-ocr` |
| Python version | 3.11 in the container (local development/tests were run on 3.14.5) |
| Install | `pip install --no-cache-dir -r backend/requirements.txt` (done in the image) |
| Start | `uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}` |
| Health endpoint | `GET /health` → `{"status":"ok","service":"BrandSentry AI","version":"0.3.0","environment":"production"}` |
| Docker HEALTHCHECK | `curl -f http://localhost:${PORT}/health` every 30s |
| Persistent storage | Needed for `$DATA_DIR` if uploaded guidelines must survive restarts (see F) |

Render: `render.yaml` is a Blueprint. Create/sync it from the Render dashboard (**New → Blueprint**, select
this repository and the `main` branch). Set `LLM_API_KEY` in the dashboard (it is `sync: false`), or leave
it empty to run fully deterministic.

Local / self-hosted alternative: `docker compose up --build` (backend on `:8000` with a named volume
`backend-data`, frontend on `:3000` via nginx).

---

## D. Frontend deployment

| Item | Value |
| :--- | :--- |
| Node version | 20 (Dockerfile/CI). Local builds verified with Node 24.16 |
| Install | `npm install` (Render) / `npm ci` (Docker) |
| Build | `npm run build` (`tsc && vite build`) |
| Output directory | `frontend/dist` |
| API URL | `VITE_API_BASE_URL` at build time (Render: `https://brandsentry-api.onrender.com`) |
| SPA routing | Render rewrite `/* → /index.html`; nginx `try_files` in `frontend/nginx.conf` |

Render build command: `cd frontend && npm install && npm run build`, publish path `./frontend/dist`.

---

## E. CORS

`backend/app/main.py` installs `CORSMiddleware` with:

- `allow_origins` = `ALLOWED_ORIGINS` (comma-separated). Render sets
  `https://brandsentry-web.onrender.com,http://localhost:5173`.
- `allow_origin_regex = https://.*\.onrender\.com` — any Render subdomain is also accepted.
- Credentials are allowed unless `*` is in the list.

**Verified locally:** a preflight from `https://brandsentry-web.onrender.com` is allowed; a preflight from
`https://evil.example.com` is rejected (HTTP 400, no `Access-Control-Allow-Origin`).

To deploy the frontend on another domain, add it to `ALLOWED_ORIGINS` and redeploy the backend. Note that the
`*.onrender.com` regex trusts every Render-hosted site; tighten it if that is not acceptable.

---

## F. Database and persistence

| Data | Location | Survives restart on Render free tier? |
| :--- | :--- | :--- |
| ChromaDB vectors | `$DATA_DIR/chroma` | **No** — free web services have an ephemeral filesystem |
| BM25 index | `$DATA_DIR/bm25` | No |
| Uploaded guideline files | `$DATA_DIR/uploads` | No |
| Document / policy registry | `$DATA_DIR/documents.db` (SQLite) | No |
| Review audit history | `$DATA_DIR/reviews.db` (SQLite) | No |
| Embedding model weights | Baked into the Docker image | Yes |

**Verified:** on 2026-10-30 the live API returned `{"total":0,"documents":[]}` from `/api/guidelines`
after a cold start — guidelines must be re-uploaded after the free instance sleeps or redeploys.

For durable storage, attach a Render persistent disk (paid plans) mounted at `/app/backend/data`, or run
`docker compose` which uses the named volume `backend-data`. SQLite and Chroma's local store support a single
backend instance only; do not scale horizontally without moving to shared storage.

---

## G. Deployment verification

Replace `$API` / `$WEB` with your URLs (Render: `https://brandsentry-api.onrender.com` and
`https://brandsentry-web.onrender.com`). Free instances can take ~45s to wake.

1. **Backend availability**
   ```bash
   curl -s --max-time 120 $API/health
   ```
   Expect `"status":"ok"`. Confirm the new release is live: `curl -s $API/openapi.json | grep -c compliance_verdict` should be ≥ 1.
2. **Frontend availability** — open `$WEB`; the header status indicator should turn connected.
3. **API connection** — browser DevTools → Network: requests go to `$API/...` with no CORS errors.
4. **Document upload** — Guidelines tab → upload `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt`;
   expect status `indexed` with 3 chunks. Or:
   ```bash
   curl -s -X POST $API/api/guidelines/upload -F "file=@BrandSentry_Sample_Marketing_Compliance_Guidelines.txt;type=text/plain"
   ```
5. **Compliance review** — Claim Review → enter
   `Our product is 100% safe for everyone. Our office is open on weekdays.` → Review Compliance.
   Expect 2 claims: claim 1 `CONTRADICTED`, claim 2 `INSUFFICIENT_EVIDENCE`.
6. **Evidence display** — claim 1 shows the citation
   "Marketing materials must not describe a product as “100% safe”." with filename and page, and a
   correction prefixed `[DRAFT — requires human review]`.

---

## H. Known limitations

- Free-tier Render: cold starts (~45s observed) and ephemeral storage (uploads, vectors and audits are lost on
  restart/redeploy).
- Single-instance design (SQLite + local Chroma).
- Optional reranker downloads from Hugging Face at first use; without network access it silently falls back
  to RRF ordering.
- OCR requires the Tesseract binary (present in the Docker image, optional locally).
- `/api/*` has no authentication or rate limiting; treat a public deployment as a demo.
- The production Docker image was not built during the final release check (local Docker daemon was not
  running); it is unchanged from the previously deployed configuration apart from application code.
- Compliance reasoning limitations are listed in `docs/FINAL_SUBMISSION_REPORT.md`.
