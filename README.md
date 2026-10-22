# BrandSentry AI — Brand Compliance & Claim Verification Platform

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://reactjs.org/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.5.9-orange.svg)](https://www.trychroma.com/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-2.0-red.svg)](https://pymupdf.readthedocs.io/)
[![Status](https://img.shields.io/badge/Phase%202-Verified%20(33%20Tests)-10B981.svg)]()

> **Hackathon Deadline:** 25 October 2026, 10:00 AM IST  
> **Round 2 Objective:** Deliver an evidence-grounded, verifiable brand compliance platform that reviews marketing copy against uploaded brand guidelines with zero hallucinated approvals.

---

## 1. Project Overview

BrandSentry AI empowers marketing, legal, and regulatory compliance teams by automatically validating creative copy, press releases, and advertising claims against official brand rulebooks.

### Current Milestone: Phase 2 Completed & Verified
* **Guideline Ingestion**: Accepts PDF and TXT files, validates content magic bytes, rejects scanned/empty files, and securely stores files in `data/uploads/`.
* **Page-Preserving Text Extraction**: Uses PyMuPDF 2.0 to extract clean digital text page by page with exact page numbers.
* **Deterministic Chunking**: Splits documents into ~400 token chunks with 50-token overlap, preserving chunk IDs and page citations.
* **CPU Embedding Generation**: Generates 384-dimensional dense vectors using local ONNX `all-MiniLM-L6-v2` running strictly on CPU.
* **Vector Store Persistence**: Indexes chunks into ChromaDB at `data/chroma/` with cosine similarity and document filtering.
* **Semantic Search API**: `POST /api/guidelines/search` retrieves top-k relevant policy clauses with similarity metrics and citations.

---

## 2. Quickstart & Local Execution

### Prerequisites
* **Operating System**: Windows / macOS / Linux
* **Python**: 3.12+ (tested on Python 3.14.5)
* **Node.js**: v20+ (tested on Node v24.16.0)

---

### Step A: Start Backend Server

```powershell
# From repository root
.\backend\venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
* **API Root**: `http://127.0.0.1:8000`
* **Swagger Docs**: `http://127.0.0.1:8000/docs`
* **Health Check**: `http://127.0.0.1:8000/health`

---

### Step B: Start Frontend Development Server

```powershell
cd frontend
npm run dev
# Open http://localhost:5173 in browser
```

---

## 3. Example API Commands

### 1. Upload & Index a Brand Guideline
```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/guidelines/upload" `
  -F "file=@sample_guideline.pdf;type=application/pdf"
```
**Response (HTTP 201 Created):**
```json
{
  "document_id": "9b7fdc73-e7b0-4903-899b-01dbc46c5ae6",
  "filename": "sample_guideline.pdf",
  "status": "indexed",
  "page_count": 2,
  "extracted_characters": 660,
  "chunk_count": 2,
  "message": "Document successfully processed, chunked, and indexed into vector store."
}
```

### 2. Search for Relevant Policy Passages
```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/guidelines/search" `
  -H "Content-Type: application/json" `
  -d '{"query": "Can we claim our product is 100% guaranteed?", "top_k": 2}'
```
**Response (HTTP 200 OK):**
```json
{
  "query": "Can we claim our product is 100% guaranteed?",
  "document_id": null,
  "total_matches": 2,
  "results": [
    {
      "chunk_id": "9b7fdc73-e7b0-4903-899b-01dbc46c5ae6_c0",
      "document_id": "9b7fdc73-e7b0-4903-899b-01dbc46c5ae6",
      "source_filename": "sample_guideline.pdf",
      "page_number": 1,
      "chunk_index": 0,
      "text": "Rule 1.2: Prohibited Superlatives: Marketing materials must never claim our product is '100% Guaranteed'...",
      "distance": 0.5614,
      "similarity_score": 0.7193
    }
  ]
}
```

---

## 4. Running Automated Tests

Run the full 33-test suite covering health checks, file validation, text extraction, chunking, embeddings, vector retrieval, and APIs:

```powershell
.\backend\venv\Scripts\pytest.exe -v
```

**Results:**
```
======================= 33 passed, 3 warnings in 24.60s =======================
```

Run frontend production build verification:
```powershell
cd frontend
npm run build
```

---

## 5. Storage & Architecture Directory Map

* **Uploaded Documents**: Stored under `data/uploads/` (UUID-prefixed, git-ignored).
* **Vector Database**: Stored under `data/chroma/` (persistent collections, git-ignored).
* **Metadata Registry**: Stored under `data/documents.db` (SQLite tracking upload status and chunk statistics).
* **Embedding Model**: `all-MiniLM-L6-v2` ONNX model cached under user directory (`.cache/chroma/onnx_models/`).

---

## 6. Phase Roadmap Status

* [x] **Phase 1**: Project initialization, environment audit, baseline health APIs.
* [x] **Phase 2**: Guideline upload, PyMuPDF extraction, chunking, embeddings, ChromaDB retrieval.
* [ ] **Phase 3**: Marketing claim extraction, hybrid search, evidence-grounded 3-way verdict engine (`SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`).
* [ ] **Phase 4**: Citation verification and policy-compliant rewrite suggestions.
* [ ] **Phase 5**: Full interactive React compliance audit dashboard.
* [ ] **Phase 6**: Reliability, adversarial test cases, and precision/recall evaluation.
* [ ] **Phase 7**: Cloud deployment with public HTTPS URL.
* [ ] **Phase 8**: Final Round 2 submission video and documentation.
