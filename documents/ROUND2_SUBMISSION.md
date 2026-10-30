# BrandSentry AI — Round 2: The Build Submission

> **Hackathon Stage:** Round 2 (The Build)  
> **Team Name:** Nexora AI  
> **Participant:** K P Chirag Guptha  
> **Registration Number:** 24MIS0369  
> **Institution:** Vellore Institute of Technology (VIT Vellore)  
> **Submission Date:** 24 October 2026  
> **Round 2 Deadline:** 25 October 2026, 10:00 AM IST  
> **Repository:** [BRAND_SENTRY_AI](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI)  
> **Live Web Application:** [https://brandsentry-web.onrender.com](https://brandsentry-web.onrender.com)  
> **Backend REST API:** [https://brandsentry-api.onrender.com](https://brandsentry-api.onrender.com)  
> **Interactive API Docs:** [https://brandsentry-api.onrender.com/docs](https://brandsentry-api.onrender.com/docs)  
> **Health Check Endpoint:** [https://brandsentry-api.onrender.com/health](https://brandsentry-api.onrender.com/health)  

---

## 1. Executive Summary

BrandSentry AI turns approved brand guidelines into a practical pre-publication review step. A user uploads a guideline document (PDF or TXT), enters marketing copy, and receives deterministic verdicts grounded directly in retrieved source passages. The application explicitly distinguishes a claim supported by verified evidence from one contradicted by policy, and from one for which the available sources are insufficient — preventing fabricated approvals.

### What Is Working in Production

* **Guideline Ingestion Engine:** Multipart upload supporting PDF and TXT with PyMuPDF digital extraction, page boundary preservation, and automatic fallback rejection for scanned non-digital PDFs.
* **Evidence-Grounded Review:** Dense vector retrieval using local ONNX `all-MiniLM-L6-v2` embeddings and persistent ChromaDB with character-exact citation substring validation.
* **Three-Way Verdict Classification:** Conservative, explainable triage: `SUPPORTED`, `CONTRADICTED`, and `INSUFFICIENT_EVIDENCE` to eliminate hallucinated approvals.
* **Deterministic Safeguards:** High-risk prohibited phrase screening (e.g. absolute guarantees, unverified superlatives) and conservative handling of missing evidence.
* **Semantic Drift Detection:** Deterministic analysis across 7 linguistic categories with severity rating (LOW/MED/HIGH), evidence phrase diffing, and conservative compliant rewrites.
* **Accessible Production Cloud:** Dockerized FastAPI backend and React + TypeScript static frontend deployed independently on Render with automated HTTPS and health check monitoring.

---

## 2. Problem Statement & Product Goal

Marketing copy is generated at high speed by distributed teams, agencies, and generative AI. However, corporate brand guidelines and legal policies are dense and trapped in PDFs.

### Product Principles Retained from Round 1

1. **Evidence Before Explanation:** No claim is marked compliant without direct character-exact substring evidence from an uploaded brand guideline.
2. **Missing Evidence ≠ Falsity:** The system strictly separates `INSUFFICIENT_EVIDENCE` from `CONTRADICTED`.
3. **Explain and Correct:** Beyond issuing a verdict, the system produces actionable explanations and conservative suggested rewrites.
4. **Human-in-the-Loop Oversight:** Designed as reviewer-augmentation software with audit evidence and confidence scores.

### Primary User Journey

`Upload Guidelines (PDF/TXT)` ➔ `Input Copy & Atomic Claim Parsing` ➔ `RAG Retrieval & Drift Triage` ➔ `Review Verdicts, Evidence & Rewrites`

---

## 3. Progress from Round 1 to Round 2

| Feature Module | Round 1 Plan | Round 2 Implementation Status | Evidence & Notes |
| :--- | :--- | :--- | :--- |
| **Guideline Ingestion** | PDF/TXT upload & parsing | **Deployed** | PyMuPDF text extraction, chunking, and MIME validation. |
| **Vector Retrieval** | ChromaDB dense search | **Deployed** | Local CPU ONNX `all-MiniLM-L6-v2` embeddings + ChromaDB. |
| **3-Way Verdict Engine** | Three-way classification | **Deployed** | `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`. |
| **Citation Grounding** | Verifiable references | **Deployed** | Character-exact substring checks matching source page text. |
| **Prohibited Phrases** | Deterministic pre-filter | **Deployed** | Regex pre-filter for absolute promises & illegal guarantees. |
| **Semantic Drift** | Planned concept | **Deployed & Tested** | 7 heuristic drift categories with diffs and rewrites (15 tests). |
| **Multi-User Workflow** | Review queue & comments | **Deferred** | Prioritized a working vertical slice for Round 2. |
| **Multi-Tenant RBAC** | Enterprise accounts | **Deferred** | Public demo mode deployed for evaluator convenience. |
| **Multimodal Vision** | Logo/color compliance | **Roadmap (R3)** | Slated as the primary focus of Round 3. |

---

## 4. System Architecture & Request Path

* **Presentation:** React 18, TypeScript, Vite, Tailwind CSS.
* **API:** FastAPI, Uvicorn, Pydantic v2 schemas.
* **Extraction:** PyMuPDF 2.0 (`fitz`).
* **Embeddings & Vector Store:** ONNX `all-MiniLM-L6-v2` (384-dim), ChromaDB on-disk storage.
* **Registry:** SQLite (`data/documents.db`).
* **Verdict Engine:** Deterministic rule engine, citation validator, and semantic drift detector.

---

## 5. Semantic Drift Detection Engine

Evaluates claim-evidence pairs across 7 categories:

1. **CERTAINTY_SHIFT:** Qualified possibility becomes an absolute promise (*"may improve"* ➔ *"always improves"*).
2. **SCOPE_EXPANSION:** Restricted audience becomes universal (*"registered users"* ➔ *"all customers"*).
3. **NUMERICAL_EXAGGERATION:** Claimed metric exceeds evidence figure (*"up to 15%"* ➔ *"85%"*).
4. **CONDITION_OMISSION:** Prerequisite removed (*"if unused within 30 days"* ➔ *"within 30 days"*).
5. **TEMPORAL_SHIFT:** Timing or frequency altered (*"within 48 hours"* ➔ *"instant dispatch"*).
6. **CAUSALITY_SHIFT:** Correlation rewritten as proven cause (*"associated with lower churn"* ➔ *"eliminates churn"*).
7. **COMPARISON_SHIFT:** Qualified comparison becomes unsupported superlative (*"competitive"* ➔ *"fastest on earth"*).

---

## 6. Demonstration Scenarios

1. **Supported Rule:** Marketing claim matching guideline passage ➔ `SUPPORTED` with page citation.
2. **Unsupported Guarantee:** "Our product is 100% guaranteed to deliver perfect results." ➔ `CONTRADICTED` with suggested rewrite.
3. **Missing Evidence:** "Our enterprise platform increases customer productivity by 85%." ➔ `INSUFFICIENT_EVIDENCE` (no hallucinated quotes).
4. **Certainty Drift:** "Our platform always improves productivity." ➔ Flags `CERTAINTY_SHIFT` (HIGH severity).
5. **Condition Omission:** "Full refunds are available within 30 days." ➔ Flags `CONDITION_OMISSION`.

---

## 7. Verification Audit (24 October 2026)

* **Backend Tests (`pytest`):** 166 passed, 0 failed, 4 warnings in 13.72s.
* **Frontend Build (`npm run build`):** 0 TypeScript errors across 1,593 modules.
* **Git Repository:** Committed and pushed to `main` branch.

---

## 8. Round 3 Roadmap

1. **Hybrid Retrieval Benchmark:** BM25 lexical search + dense vector ChromaDB with Reciprocal Rank Fusion (RRF).
2. **Policy Governance:** Guideline version snapshots, revision diffs, reviewer approval lifecycle, and PDF audit export.
3. **Multimodal Compliance:** Image and banner asset upload with OCR text extraction, brand color hex checks, and logo boundary rules.

---

## 9. Official Submission & Team Metadata

* **Team Name:** Nexora AI
* **Participant Full Name:** K P Chirag Guptha
* **Registration Number:** 24MIS0369
* **Institution:** Vellore Institute of Technology (VIT Vellore)
* **Working Web Application:** [https://brandsentry-web.onrender.com](https://brandsentry-web.onrender.com)
* **Backend REST API:** [https://brandsentry-api.onrender.com](https://brandsentry-api.onrender.com)
* **API Documentation:** [https://brandsentry-api.onrender.com/docs](https://brandsentry-api.onrender.com/docs)
* **Backend Health Check:** [https://brandsentry-api.onrender.com/health](https://brandsentry-api.onrender.com/health)
* **Source Code Repository:** [https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI)
