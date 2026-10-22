# BrandSentry AI — Feature Implementation Checklist

> **Hackathon Deadline:** 25 October 2026, 10:00 AM IST  
> **Rule:** Do not mark a feature as IMPLEMENTED merely because its folder or interface exists. A feature is only `TESTED` once verified through automated test suites or live end-to-end verification.

### Status Taxonomy:
* `NOT STARTED` — Planned but no implementation started.
* `IN PROGRESS` — Active development underway.
* `IMPLEMENTED` — Code written but comprehensive tests not completed.
* `TESTED` — Code complete and verified through automated test suites and smoke runs.
* `BLOCKED` — Execution hindered by external blocker or missing dependency.

---

## P0 — Mandatory Core Features (Target: Phase 2 through Phase 7)

| Feature ID | Feature Name | Description | Target Phase | Current Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P0-01** | **Project & Environment Setup** | Full-stack scaffolding, dependencies, build pipelines, health endpoint | Phase 1 | **TESTED** | FastAPI GET /health passing (pytest: 3/3 passed). React build (tsc + vite) passing. |
| **P0-02** | **PDF/TXT Guideline Upload** | Multi-part upload handler for brand guideline documents | Phase 2 | **NOT STARTED** | Backend storage & upload endpoint targeted for Phase 2. |
| **P0-03** | **Text Extraction Engine** | Clean text extraction using PyMuPDF preserving page numbers & sections | Phase 2 | **NOT STARTED** | PyMuPDF pipeline targeted for Phase 2. |
| **P0-04** | **Document Chunking** | Section-aware semantic chunking (~300–500 tokens) with metadata | Phase 2 | **NOT STARTED** | Metadata schema prepared in Phase 1 schemas. |
| **P0-05** | **Embedding Generation** | Dense vector embeddings via SentenceTransformers or remote provider | Phase 2 | **NOT STARTED** | Abstracted interface to be implemented in Phase 2. |
| **P0-06** | **Vector Retrieval** | Persistent ChromaDB collection indexing with top-k similarity search | Phase 2 | **NOT STARTED** | ChromaDB persistence path configured in `backend/app/core/config.py`. |
| **P0-07** | **Marketing Content Input** | Text input interface for raw advertising and marketing copy | Phase 3 / 5 | **NOT STARTED** | Frontend component queued for Phase 5. |
| **P0-08** | **Claim Extraction** | Decompose unstructured marketing copy into discrete, testable claims | Phase 3 | **NOT STARTED** | Extraction logic queued for Phase 3. |
| **P0-09** | **Three-Way Verdict Engine** | Rigorous evaluation: SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE | Phase 3 | **NOT STARTED** | Strict rule: No automatic approval on missing evidence. |
| **P0-10** | **Verifiable Policy Citations** | Exact guideline document name, page number, and quote snippet | Phase 4 | **NOT STARTED** | Hallucination-prevention check queued for Phase 4. |
| **P0-11** | **Suggested Corrections** | Compliant marketing rewrites for contradicted & insufficient claims | Phase 4 | **NOT STARTED** | Prompt & rule-guided rewrite generator. |
| **P0-12** | **Complete Review Workflow** | End-to-end flow from guideline upload to correction application | Phase 5 | **NOT STARTED** | Primary hackathon deliverable. |
| **P0-13** | **Graceful Error Handling** | Structured error responses, offline backend detection, retry options | All Phases | **IN PROGRESS** | Implemented & tested for health checks; to be expanded across all APIs. |
| **P0-14** | **Public Deployment** | Cloud container deployment with public HTTPS URL for judges | Phase 7 | **NOT STARTED** | Targeted after Phase 6 testing. |

---

## P1 — Post-Core Enhancements (High Priority)

| Feature ID | Feature Name | Description | Target Phase | Current Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P1-01** | **Deterministic Pre-Filter** | Regex/keyword screener for banned words and trademark casing | Phase 3 | **NOT STARTED** | Eliminates LLM latency/cost for obvious violations. |
| **P1-02** | **Semantic Drift Detection** | Measures divergence between claim claims and original brand positioning | Phase 4 | **NOT STARTED** | Queued for Phase 4. |
| **P1-03** | **Claim-Type Retrieval Routing** | Category-based query expansion (Regulatory, Product, Voice) | Phase 3 | **NOT STARTED** | Optimizes hybrid recall per claim type. |
| **P1-04** | **Review History** | Session audit log tracking past copy iterations and compliance scores | Phase 5 | **NOT STARTED** | Client-side or SQLite session storage. |
| **P1-05** | **Exportable Review Reports** | PDF/JSON compliance summary export for legal/audit records | Phase 5 | **NOT STARTED** | Generates auditable compliance sign-off report. |

---

## P2 — Future Work & Research Roadmap

| Feature ID | Feature Name | Description | Target Phase | Current Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P2-01** | **Graph-Based Policy Reasoning** | Neo4j/Knowledge Graph for complex hierarchical brand rules | Post-Hackathon | **NOT STARTED** | Architectural extension. |
| **P2-02** | **Feedback-Driven Improvement** | Human-in-the-loop review feedback to fine-tune retrieval prompts | Post-Hackathon | **NOT STARTED** | Enterprise feature. |
| **P2-03** | **Multimodal Visual Compliance** | Image & video brand logo, color palette, and layout audit | Post-Hackathon | **NOT STARTED** | Vision model integration. |
| **P2-04** | **Calibrated Confidence Scoring** | Probabilistic confidence calibration across verdict categories | Post-Hackathon | **NOT STARTED** | Advanced ML feature. |
| **P2-05** | **Enterprise-Scale Infrastructure** | Distributed queue (Celery/Redis), multi-tenant auth, Kubernetes | Post-Hackathon | **NOT STARTED** | Deferred per hackathon constraints. |

---

## Summary of Current Milestone Progress (Phase 1)
- **Features Tested & Passing**: 1 (`P0-01: Project & Environment Setup`)
- **Features In Progress**: 1 (`P0-13: Graceful Error Handling`)
- **Features Not Started**: 17
- **Features Blocked**: 0
