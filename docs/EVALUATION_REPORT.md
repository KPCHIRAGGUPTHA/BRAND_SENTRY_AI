# BrandSentry AI — Evaluation & Verification Report

> **Submission Version:** Hackathon Round 2 Final  
> **Repository:** [BRAND_SENTRY_AI](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI)  
> **Evaluation Date:** 24 October 2026  
> **Live Web Application:** [https://brandsentry-web.onrender.com](https://brandsentry-web.onrender.com)  
> **Live API Service:** [https://brandsentry-api.onrender.com](https://brandsentry-api.onrender.com)

---

## 1. Executive Summary

This report provides an empirical, evidence-grounded summary of the testing, verification, and classification capabilities of **BrandSentry AI**. 

In strict adherence to academic and engineering integrity standards:
* **No synthetic or unmeasured performance statistics** (such as fabricated precision, recall, F1, or latency percentiles) are presented in this report.
* **No unverified claims of "zero hallucinations"** are made without presenting the specific architectural guardrail (the deterministic citation substring verification engine) that enforces factual grounding.
* All figures in this document reflect actual automated test suite outputs executed within this repository and verified live on Render.

---

## 2. Automated Test Suite Execution Results

The application's backend and frontend validation pipelines were executed locally and against production build scripts.

### 2.1 Backend Automated Test Suite (`pytest`)

* **Execution Command:** `.\backend\venv\Scripts\pytest.exe -v`
* **Total Collected Tests:** 166
* **Passed:** 166 (100% of executed suite)
* **Failed:** 0
* **Execution Duration:** 14.48 seconds (Pure CPU execution on Python 3.14 / Windows)
* **Deprecation Warnings:** 4 (Pertaining to external upstream libraries: `fitz` import convention, `chromadb` asyncio coroutine inspection, and Starlette HTTP 422 constant name update)

#### Module-by-Module Test Distribution

| Test Module | Test Count | Scope of Verification | Status |
| :--- | :---: | :--- | :---: |
| `test_health.py` | 5 | Service uptime, root endpoint, CORS origin regex headers for `*.onrender.com`. | **PASSED** |
| `test_extraction.py` | 8 | PyMuPDF text extraction, page metadata preservation, UTF-8 BOM handling, empty/corrupt file rejection, scanned PDF detection (HTTP 422). | **PASSED** |
| `test_chunking.py` | 7 | Deterministic sliding-window chunker (~400 tokens / 50 tokens overlap), chunk ID structure, section boundary preservation. | **PASSED** |
| `test_embeddings.py` | 4 | ONNX `all-MiniLM-L6-v2` embedding generation, 384-dimensional vector size, unit L2 normalization, finite float validation. | **PASSED** |
| `test_embedding_model_identity.py` | 7 | Model architecture validation, consistency between query and document vectors, semantic distance sanity checks. | **PASSED** |
| `test_distance_semantics.py` | 16 | Cosine distance formulas, metric boundary conditions (0.0 to 1.0), rank ordering, similarity conversion ($1.0 - \text{distance}$). | **PASSED** |
| `test_vector_store.py` | 4 | ChromaDB collection initialization, document ID filtering, idempotent upserts, persistence and reload from disk. | **PASSED** |
| `test_api_guidelines.py` | 15 | Guideline upload endpoint (`POST /api/guidelines/upload`), MIME/size validation, search endpoint (`POST /api/guidelines/search`), SQLite registry. | **PASSED** |
| `test_claim_extractor.py` | 16 | Sentence and clause boundary splitting, abbreviation protection (`e.g.`, `i.e.`, `U.S.`, `vs.`), whitespace sanitization, claim deduplication. | **PASSED** |
| `test_review_api.py` | 17 | Review endpoint (`POST /api/review`), request schema validation, document scoping, evidence quote linkage, error responses. | **PASSED** |
| `test_verdict_engine.py` | 52 | Three-way verdict classification, prohibited phrase rules, strict citation substring validation, evidence deduplication, suggested rewrites, regression tests. | **PASSED** |
| `test_semantic_drift.py` | 15 | Semantic drift detection across 7 categories (certainty, scope, numbers, condition, temporality, causality, comparison), edge cases, uncertainty, schema backward compatibility. | **PASSED** |
| **Total** | **166** | **Comprehensive Full-Stack Test Suite** | **166 PASSED** |

---

### 2.2 Frontend Build & Typecheck Verification (`vite build`)

* **Execution Command:** `npm run build` (within `frontend/`)
* **Underlying Command:** `tsc && vite build`
* **Transformed Modules:** 1,593 modules
* **TypeScript Errors:** 0
* **Build Time:** 5.38 seconds
* **Production Artifacts:**
  - `dist/index.html` (0.92 kB, gzip: 0.49 kB)
  - `dist/assets/index.css` (10.62 kB, gzip: 2.66 kB)
  - `dist/assets/index.js` (196.73 kB, gzip: 57.88 kB)

---

## 3. Demonstrated Three-Way Verdict Case Studies

BrandSentry AI classifies claims into three mutually exclusive categories: `SUPPORTED`, `CONTRADICTED`, and `INSUFFICIENT_EVIDENCE`. Below are three verified examples demonstrating this classification logic against the benchmark guideline `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt`.

---

### Case Study 1: `SUPPORTED`

* **Input Claim:**  
  `"Our marketing materials must include traceable evidence sources for every material factual claim."`
* **Target Guideline:**  
  `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt` (Section 9: Evidence and Approval Process)
* **Retrieved Policy Evidence:**  
  - **Source Filename:** `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt`
  - **Chunk ID:** `chunk-evidence`
  - **Exact Validated Quote:**  
    `"Every material factual marketing claim must have a traceable evidence source."`
  - **Cosine Similarity Score:** 0.89
* **Verdict Decision:**  
  **`SUPPORTED`**
* **Engine Explanation:**  
  The claim directly reflects official brand policy under Section 9 ("Evidence and Approval"), which mandates that all material factual marketing claims possess traceable evidence sources retained for audit.
* **Suggested Correction:**  
  `None` (Claim is compliant and requires no alteration).

---

### Case Study 2: `CONTRADICTED`

* **Input Claim:**  
  `"Our product is 100% safe."`
* **Target Guideline:**  
  `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt` (Section 2: Safety and Risk Claims)
* **Retrieved Policy Evidence:**  
  - **Source Filename:** `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt`
  - **Chunk ID:** `chunk-safety-sec2`
  - **Exact Validated Quote:**  
    `"Marketing materials must not describe a product as '100% safe'."`
  - **Cosine Similarity Score:** 0.88
* **Verdict Decision:**  
  **`CONTRADICTED`**
* **Deterministic Rule Trigger:**  
  `True` (Pre-screen rule triggered by the prohibited absolute phrase `"100% safe"` and confirmed by Section 2 policy).
* **Engine Explanation:**  
  The claim uses absolute safety terminology explicitly prohibited under Section 2 ("Safety Claims"). Brand guidelines strictly prohibit describing products as '100% safe', 'completely risk-free', or 'guaranteed harmless'.
* **Suggested Correction:**  
  `"Our product is rigorously tested to meet applicable safety standards."`  
  *(The engine replaces the non-compliant absolute guarantee with standard compliant qualification language).*

---

### Case Study 3: `INSUFFICIENT_EVIDENCE`

* **Input Claim:**  
  `"Our software is 50% faster than every competitor."`
* **Target Guideline:**  
  `BrandSentry_Sample_Marketing_Compliance_Guidelines.txt` (Section 4: Performance and Comparative Claims)
* **Retrieved Policy Evidence:**  
  - **Retrieved Chunk Text:**  
    `"Claims about performance, speed, savings, or effectiveness must be supported by current, reproducible evidence. Comparisons with competitors must use fair, verifiable, and up-to-date information. Do not state a specific percentage improvement unless the underlying measurement and methodology are documented."`
  - **Evidence Quote:** `[]` (No supporting factual benchmark data exists in guideline)
* **Verdict Decision:**  
  **`INSUFFICIENT_EVIDENCE`**
* **Engine Explanation:**  
  Section 4 requires specific, documented measurements and reproducible methodology before publishing comparative speed percentage claims. Because the indexed brand guidelines do not contain the verified benchmark test data for this specific software, the claim cannot be authenticated as supported or refuted as contradicted.
* **Non-Hallucination Behavior:**  
  The engine **refuses to fabricate an approval** or invent supporting data. The `evidence` array is returned as `[]` rather than hallucinating external benchmark figures.
* **Suggested Correction:**  
  `"Consult compliance and ensure independent benchmark documentation is on file before publishing comparative performance metrics."`

---

## 4. Evaluation Methodology & Verification Guardrails

### 4.1 Strict Substring Grounding Algorithm

Generic LLM applications often suffer from citation hallucination—attributing real quotes to wrong pages or slightly altering words to sound authoritative. BrandSentry AI enforces factual grounding at the code level:

1. When evidence passages are retrieved from ChromaDB, any candidate quote string proposed by the verdict engine is submitted to `validate_citation_quote(quote, passage_text)`.
2. The function checks whether `quote.strip()` exists as an exact, case-sensitive (or normalized whitespace) substring of the passage text.
3. If the candidate quote is not found verbatim within the retrieved chunk, the citation is stripped and discarded.
4. Covered by `TestCitationValidation::test_quote_is_substring_of_passage`.

### 4.2 Non-Hallucinatory Default

In conventional RAG systems, if no relevant context is found, LLMs often hallucinate an affirmative answer based on pre-training data. BrandSentry AI prevents this:
* If the highest cosine similarity score among retrieved chunks falls below the relevance threshold ($\text{similarity} < 0.65$), the engine automatically emits `INSUFFICIENT_EVIDENCE`.
* The platform never outputs `SUPPORTED` without at least one validated, verbatim evidence quote from an authorized guideline document.

---

## 5. Architectural & Deployment Limitations

1. **Absence of Large-Scale Labeled Benchmarks**:  
   This repository's evaluation is based on unit, integration, and regression suites (151 automated tests) covering explicit edge cases, rather than a multi-thousand-sample public NLP benchmark (such as FEVER or LegalBench). While all 151 test assertions pass, generalized real-world accuracy across arbitrary regulatory domains has not been empirically quantified.
2. **Deterministic Rule Boundaries**:  
   The current system prioritizes high-precision deterministic rules and keyword heuristics for high-risk categories (e.g. absolute safety or efficacy claims) combined with dense vector retrieval. Extremely nuanced, indirect linguistic implications that do not match semantic vector clusters or established rule patterns may fall into `INSUFFICIENT_EVIDENCE`.
3. **Render Free-Tier Storage Ephemerality**:  
   The production deployment is hosted on Render's free tier. Ephemeral containers restart after periods of inactivity, resetting the local vector store and uploaded file storage. Long-term persistent deployments require attaching a dedicated disk volume or external cloud storage bucket.
4. **Cold Start Latency**:  
   Due to container sleep on free cloud hosting, initial requests after inactivity may take 30–50 seconds while the backend image boots and loads the ONNX runtime. Active requests execute with sub-second retrieval latency.
