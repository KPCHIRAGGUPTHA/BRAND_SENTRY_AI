# BrandSentry AI — Final Submission Report

**Date:** 2026-10-30  
**Repository:** https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI  
**Submission branch:** `main`

Every result below was produced during the final release check on 2026-10-30 unless it is explicitly
labelled as a previously recorded result.

---

## 1. Project

**BrandSentry AI** is an AI-powered, evidence-grounded, human-in-the-loop compliance review assistant. It
checks marketing claims against regulatory and organizational guidelines that the user uploads. It is a
review aid. It does not approve content autonomously.

### Architecture

```
React 18 + TypeScript + Vite (static site)
        │  HTTPS / JSON (VITE_API_BASE_URL, CORS)
        ▼
FastAPI + Pydantic v2 (Uvicorn, Docker, Python 3.11)
  ├─ /api/guidelines   upload (PDF/TXT) → extract → chunk → embed → index; search; policy versions
  ├─ /api/review       claim extraction → hybrid retrieval per claim → verdict engine → audit record
  │                    (+ image OCR review via Tesseract)
  ├─ /api/reviews      audit history, stats, JSON/CSV/PDF export
  └─ /health
Storage ($DATA_DIR): ChromaDB (dense vectors), BM25 JSON index, uploads/, documents.db, reviews.db (SQLite)
```

### Technology stack

| Layer | Technology |
| :--- | :--- |
| Frontend | React 18.3, TypeScript, Vite 6, lucide-react, Vitest |
| Backend | Python, FastAPI, Pydantic v2 / pydantic-settings, Uvicorn |
| Retrieval | ChromaDB + `all-MiniLM-L6-v2` (ONNX), `rank-bm25`, Reciprocal Rank Fusion (k=60), optional ONNX cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` |
| Reasoning | Deterministic verdict engine. An optional LLM path is used only when `LLM_API_KEY` is set. |
| Documents / OCR | PyMuPDF, Tesseract + Pillow |
| Persistence | ChromaDB persistent client, SQLite |
| Reports | ReportLab (PDF), CSV, JSON |
| Hosting | Render Blueprint (`render.yaml`): Docker web service + static site |

### Major capabilities

- Per-claim extraction with negation and disclaimer handling, and prompt-injection boundaries
- Hybrid dense + BM25 retrieval with RRF, scoped to the selected documents and policy versions
- Three-way verdicts (`SUPPORTED` / `CONTRADICTED` / `INSUFFICIENT_EVIDENCE`) where `verdict == compliance_verdict`
- Verbatim citations taken from retrieved passages, with filename and page
- Universal risk warnings kept separate from organization guideline violations
- Draft corrections labelled `[DRAFT — requires human review]`
- Semantic drift detection, policy versioning, a persistent audit trail and multi-format export

---

## 2. Verification

### 2.1 Backend tests: **PASSED**

`backend/venv/Scripts/python.exe -m pytest -q` (Python 3.14.5, Windows):

| Run | Result |
| :--- | :--- |
| `round-3-final`, before release commits | **270 passed**, 0 failed, 0 skipped, 5 warnings (upstream deprecations) |
| `main`, after merge | **270 passed**, 0 failed, 0 skipped, 5 warnings |
| `main` + Python 3.11 fix, run on **Python 3.11.16** (the CI and Docker runtime) in an isolated venv | **270 passed**, 0 failed, 4 warnings |

**Blocker found after the push and fixed:** CI on merge commit `88cfcec` failed with pytest exit code 2.
I reproduced the failure under Python 3.11: `backend/app/api/review.py` used `Tuple` in a return annotation
without importing it. Commit `41b6241` introduced this before the release. Python 3.14 evaluates
annotations lazily, so local runs passed. On Python 3.11, which CI and the `python:3.11-slim` production
image both use, the backend crashed on import with `NameError`. The fix is a one-line import
(`from typing import Optional, List, Tuple`), verified on both 3.11 and 3.14.

### 2.2 Frontend: **PASSED**

| Check | Result |
| :--- | :--- |
| `npm run build` (`tsc && vite build`) | Succeeded on the dev branch and on `main` after the merge (~239 kB JS, 66 kB gzip) |
| `npx vitest run` | **15 passed** (3 files) on the dev branch and on `main` |

### 2.3 End-to-end checks against a real local backend: **PASSED, with one finding**

The backend ran under Uvicorn with an isolated, empty `DATA_DIR`. Nothing was mocked.

| # | Check | Result |
| :--- | :--- | :--- |
| 1 | `GET /health` | 200, `status: ok` |
| 2 | Upload `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt` | 201, `indexed`, 3 chunks |
| 3 | Re-upload the same file | 201, "Document already indexed. Existing record reused." |
| 4 | Upload a PDF (`tests/ui/fixtures/sample_guideline.pdf`) | 201, `indexed`, 1 chunk |
| 5 | Review of 3 claims scoped to the sample guideline | 3 claims extracted; `100% safe` → `CONTRADICTED` with a verbatim citation (the substring was checked against the source file); office hours → `INSUFFICIENT_EVIDENCE` |
| 6 | `verdict == compliance_verdict` | Held for every claim |
| 7 | Document isolation (review scoped to the PDF only) | Evidence came only from `sample_guideline.pdf` |
| 8 | Invalid upload (`.csv`) | 400, "accepts .pdf and .txt guidelines only" |
| 9 | Empty upload | 400, "uploaded file is empty (0 bytes)" |
| 10 | Empty review content | 422 validation error |
| 11 | Unknown document id | 404 "not found in registry" |
| 12 | CORS preflight | Allowed for `https://brandsentry-web.onrender.com`; rejected (400) for `https://evil.example.com` |
| 13 | Audit history `GET /api/reviews` | 200, the review was persisted |
| 14 | UI in a browser (Vite dev server → local API) | Guideline list loaded. Review submitted from the UI. Summary, claims, risk warning, explanation, correction and citations with RRF/BM25/similarity scores all rendered. |
| 15 | UI when the backend is unreachable (CORS blocked) | Showed a "Failed to fetch" error. It did not show a false success. |
| 16 | UI at 375 px width | Usable, but the page overflows horizontally (scrollWidth 1089 px). This is a known limitation. |

**Defect found and fixed:** the risk-warning panel always appended "(No specific organizational policy chunk
found)", including when the verdict was `CONTRADICTED` and grounded in a cited guideline chunk. That text
contradicted the evidence shown below it. It is now shown only when the claim has no evidence. The fix was
re-verified in the browser.

**Finding not fixed (documented):** the claim "Customer data is completely secure and impossible to hack."
returned `INSUFFICIENT_EVIDENCE`, even though section 8 of the sample guideline prohibits that wording. The
correct chunk was retrieved (it ranked first under BM25 and RRF), but its dense similarity was 0.228, below the
0.25 evidence threshold. The chunk is long and covers several topics, which dilutes its similarity score. This
is a conservative miss, not a false approval. I did not change the calibrated threshold or the chunking at
submission time.

### 2.4 Deployment checks

| Check | Result |
| :--- | :--- |
| `https://brandsentry-web.onrender.com/` | **Verified**: HTTP 200 |
| `https://brandsentry-api.onrender.com/health` | **Verified**: HTTP 200 `{"status":"ok","version":"0.3.0","environment":"production"}`. The first request took 43.6 s (cold start). |
| `GET /api/guidelines` on the live API | **Verified**: `{"total":0}` after a cold start, confirming ephemeral storage |
| Live code version before the merge | The OpenAPI schema had no `rrf_score` or `compliance_verdict`, so the service was running pre-Round-3 code (the old `main`) |
| Live code version after the push | **Not updated.** I polled `/openapi.json` for about 27 minutes after pushing `88cfcec` and the service still ran the old code. See section 4. |
| Production Docker image build | **Not tested.** The local Docker daemon was not running. |
| GitHub Actions run [41095740924](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI/actions/runs/41095740924) on `88cfcec` | The Chrome install step passed after the CI fix. Dependency install and the frontend build passed. **Backend unit tests failed** (the Python 3.11 `NameError` above), so the Selenium steps were skipped. A new run is triggered by the fix commit; check the Actions tab for its result. |
| GitHub Actions run [41101181893](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI/actions/runs/41101181893) on `597a59f` | **Failed** (exit code 1, 5m37s). The run uploaded the `selenium-failure-diagnostics` artifact, which only the Selenium UI step produces. That points to the backend unit tests passing and the Selenium suite failing, but I could not confirm it: viewing the logs requires signing in to GitHub. The Selenium suite was not run locally either. |

### 2.5 Not tested or blocked

- Image OCR review end to end in the browser (unit tests cover it; it was not run manually)
- Uploading a file through the browser UI (the API upload was verified; the UI file picker was not driven)
- Optional reranking mode and the optional LLM path (both off in the production configuration)
- Selenium UI suite (`tests/ui`) run locally

---

## 3. Git release

| Item | Value |
| :--- | :--- |
| Original branch | `round-3-final` @ `41b6241`, with 16 modified and 45 untracked files |
| Recovery points | Local branch `backup/round-3-final-pre-release` @ `41b6241`, plus a tar archive of all uncommitted files taken before any change |
| Release commits on `round-3-final` | `1fb23e0` feat(engine): Stage 1–3.5 compliance reasoning, optional reranking, and holdout evaluation; `af15951` chore(release): prepare BrandSentry AI final submission |
| Merge | `88cfcec`: a `--no-ff` merge of `round-3-final` into `main`, with no conflicts. `origin/main` (`48d2fb5`) was already an ancestor, so the merge did not diverge. |
| Push | `48d2fb5..88cfcec main -> main` and `41b6241..af15951 round-3-final -> round-3-final`. Both were normal pushes, with no force. |
| Post-merge fix | The Python 3.11 import fix and this report were committed on `main`. `round-3-final` was then fast-forwarded to the same commit, and both branches were pushed normally. |
| Final branch | `main` |
| Development branch | `round-3-final` is kept locally and on GitHub |

**Not committed, on purpose:** these one-off debugging helpers stay in the working directory, untracked:
`backend/evaluation/{check_dev,debug_dev_failures,debug_failures,debug_reg,inspect_corpus,summarize_results,test_why}.py`.

**Other remote branch:** `origin/feat/hackathon-round3-1846641142607525942` exists on GitHub. Its origin is
unknown and it was not merged. Its CI fix (dropping `libgconf-2-4`) was applied independently.

---

## 4. Deployment

| Item | Value |
| :--- | :--- |
| Frontend URL | https://brandsentry-web.onrender.com (**verified**: reachable) |
| Backend URL | https://brandsentry-api.onrender.com (**verified**: reachable) |
| Health endpoint | https://brandsentry-api.onrender.com/health |
| API docs | https://brandsentry-api.onrender.com/docs |
| Hosting | Render, defined in `render.yaml`: Docker web service `brandsentry-api` (free plan, Oregon) and static site `brandsentry-web` |
| Backend build/start | `Dockerfile.backend`: `pip install -r backend/requirements.txt`; `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| Frontend build | `cd frontend && npm install && npm run build`, publishing `frontend/dist` |
| Required env | `ALLOWED_ORIGINS` and `VITE_API_BASE_URL`. `LLM_API_KEY` is optional and set only in the dashboard. |
| Persistence | Ephemeral on the free tier. Uploads, ChromaDB, BM25 and SQLite are lost on restart or redeploy. |

**Auto-deploy status: not confirmed. The live service is still running pre-Round-3 code.** After the push
to `main`, the live OpenAPI schema still had no `compliance_verdict` field for about 27 minutes. I have no
access to the Render dashboard, so I could not tell whether auto-deploy is turned off, deploys from another
branch, or failed. One possible cause is that a deploy of `88cfcec` would have crashed at startup because of the
Python 3.11 `NameError` described in 2.1. The fix commit on `main` resolves that.

**Manual steps (Render dashboard):**
1. Open `brandsentry-api` → **Settings** and confirm that **Branch = `main`** and Auto-Deploy is on.
2. Open **Events / Deploys** and check whether a deploy of `88cfcec` failed. If so, its logs should show the `NameError`.
3. Click **Manual Deploy → Deploy latest commit** for `brandsentry-api`, then for `brandsentry-web`.
4. Confirm `LLM_API_KEY` is set (or deliberately left empty) under **Environment**. Do not paste it anywhere else.
5. Verify the release with `curl -s https://brandsentry-api.onrender.com/openapi.json | grep -c compliance_verdict`. The result should be ≥ 1. Then follow the steps in `DEPLOYMENT.md` section G.

Full configuration and verification steps are in [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## 5. Evaluation results (previously recorded, files in `backend/evaluation/results/`)

| Set | N | Hybrid accuracy | Dense accuracy |
| :--- | ---: | ---: | ---: |
| Development (used during tuning) | 60 | 96.67% | 95.00% |
| Independent holdout | 118 | 78.81% | 80.51% |
| Blind challenge | 32 | 75.00% | 71.88% |

On the holdout set, hybrid produced 2 false-positive SUPPORTED verdicts and 11 false-positive CONTRADICTED
verdicts. The development-set figure is optimistic because the system was tuned against that set.

---

## 6. Remaining limitations

### Compliance reasoning
- False-positive contradictions in some operational contexts. This is the largest failure class on the holdout set.
- Weak on conditional approvals and policy nuance (holdout `conditional_approval` category: 1 of 6 correct).
- Edge cases where documents serve as evidence.
- Conservative `INSUFFICIENT_EVIDENCE` when the relevant rule sits in a long chunk that covers many topics (see 2.3).
- Small benchmarks (60, 118 and 32 cases), so results may not generalize.
- Verdicts require human review. The product must not be presented as autonomous or perfectly accurate.

### Deployment
- Free-tier cold starts (about 45 s observed) and ephemeral storage
- Single-instance design (SQLite and a local ChromaDB)
- No authentication or rate limiting on the public API
- The CORS regex accepts any `*.onrender.com` origin
- The optional reranker downloads its model from Hugging Face on first use

### Not fully verified
- Building the production Docker image locally
- Deployment of this release to Render (the live service still runs older code; see section 4)
- The CI run for the fix commit, including the Selenium UI suite
- OCR review and browser file upload in the UI
- Mobile layout (it overflows horizontally)
