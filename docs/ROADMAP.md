# BrandSentry AI — Product & Engineering Roadmap

> **Platform Version:** 0.3.0 Production Ready  
> **Submission:** Round 3: The Final Round  
> **Last Updated:** October 2026  

---

## 🎯 Status Classification Overview

To maintain complete transparency and avoid claiming unverified capabilities, roadmap items are categorized by lifecycle maturity:

- **COMPLETED**: Fully implemented, tested across automated suites, and verified in production architecture.
- **NEXT 30 DAYS**: Near-term enhancements currently prioritized for post-hackathon sprint.
- **NEXT 60–90 DAYS**: Enterprise features addressing organizational workflows and collaboration.
- **LONGER TERM**: Strategic platform innovations and multimodal expansions.

---

## ✅ COMPLETED (Implemented & Verified in Round 3)

### Hybrid Retrieval & Evaluation (Improvement 1)
- [x] **BM25Okapi Lexical Indexing**: Tokenized inverted index over guideline passages with multi-document scoping and JSON persistence (`bm25_retriever.py`).
- [x] **Reciprocal Rank Fusion (RRF)**: Fusion algorithm ($k=60$) blending dense ChromaDB vectors with BM25 ranks (`hybrid_retriever.py`).
- [x] **Passage Deduplication**: Eliminates near-identical and redundant retrieved passages based on normalized text similarity.
- [x] **Dynamic Mode Switching**: Supports runtime selection between `hybrid`, `dense`, and `bm25` retrieval modes.
- [x] **Labelled Benchmark Suite**: 60-case ground-truth dataset across 10 failure categories (`retrieval_benchmark.jsonl`).
- [x] **Empirical Metrics Measurement**: Rigorous automated calculation of Precision@3/5, Recall@3/5, MRR, Verdict Accuracy, and Latency (`docs/RETRIEVAL_EVALUATION.md`).

### Policy Governance & Auditing (Improvement 2)
- [x] **Immutable Policy Versioning**: SQLite `policy_versions` schema tracking version UUIDs, labels (`v1.0`, `v2.0`...), and SHA-256 hashes.
- [x] **Active Version Activation**: Safe atomic version toggling with rollback capabilities.
- [x] **Persistent Review Audit Storage**: SQLite `reviews.db` recording review UUID, timestamp, marketing content, source, policy versions, and full claims JSON.
- [x] **Audit History API**: Paginated `GET /api/reviews` with source filtering and detail inspection (`GET /api/reviews/{id}`).
- [x] **Multi-Format Export Engine**: On-demand generation of RFC-compliant CSV, structured JSON, and styled ReportLab PDF reports.
- [x] **Live Analytics Dashboard**: Real-time aggregation of reviews, claim distributions, and recent audit logs (`Dashboard.tsx`).

### Multimodal Visual Compliance (Improvement 3)
- [x] **Image Decoding & Validation**: Pillow validation verifying formats (PNG, JPEG, WebP), dimensions (10px to 8000px), and size (10MB limit).
- [x] **Tesseract OCR Extraction**: Structured text extraction with word-level bounding boxes and confidence scoring (`ocr_service.py`).
- [x] **Human-in-the-Loop UI**: Promotional creative upload, thumbnail preview, OCR confidence gauge, and interactive text correction editor (`ClaimReview.tsx`).
- [x] **Compliance Engine Reuse**: Direct routing of user-verified image text into existing claim extraction, hybrid retrieval, and verdict engine.
- [x] **Traceable Image Audit**: Permanent recording of `review_source="image"`, raw OCR text, and user-corrected text.

---

## 📅 NEXT 30 DAYS

- **Retrieval Benchmark Expansion**:
  - Expand benchmark from 60 to 250+ annotated enterprise advertising disputes across financial services, pharmaceuticals, and direct-to-consumer retail.
  - Benchmark performance across varying chunk sizes (200, 300, 500 words).
- **Evidence Selection Optimization**:
  - Implement dynamic cross-encoder reranking (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) for ambiguous or multi-clause claims within latency constraints.
- **OCR Quality Enhancements**:
  - Add adaptive binarization (Otsu thresholding) for low-contrast text on photographic promotional backgrounds.
  - Multi-language OCR configuration for localized marketing collateral.
- **Audit History Filtering**:
  - Date-range filtering, verdict-status filtering (show only reviews containing contradicted claims), and free-text search across past marketing copy.
- **Report Customization**:
  - Custom branding headers (company logo, legal entity name) on generated PDF audit certificates.

---

## 🏢 NEXT 60–90 DAYS

- **Role-Based Access Control (RBAC)**:
  - User roles (Marketer, Compliance Officer, Legal Counsel, Administrator) with distinct permissions.
- **Collaborative Approval Workflows**:
  - In-app sign-off mechanism allowing legal teams to formally approve or request revisions on flagged claims.
- **Reviewer Annotations**:
  - Interactive commenting and inline margin notes attached to specific claim verdicts.
- **Expanded Policy Formats**:
  - Direct ingestion of Microsoft Word (`.docx`), HTML web guidelines, and Confluence wiki spaces.
- **Enterprise Storage Connectors**:
  - S3 / Google Cloud Storage drivers for persistent storage of uploaded guidelines and generated PDF audit reports.
- **Production Observability**:
  - Prometheus metrics exporter and OpenTelemetry tracing for monitoring retrieval latency percentiles ($p_{95}, p_{99}$).

---

## 🌐 LONGER TERM (Strategic Vision)

- **Multilingual Compliance Review**:
  - Native cross-lingual retrieval enabling marketing campaigns in European and Asian markets to be verified against global English brand policies.
- **Visual Identity & Layout Compliance**:
  - Deep learning models evaluating logo safe zones, minimum spacing, trademark positioning, and brand color palette hex accuracy.
- **Marketing Platform Integrations**:
  - Direct integrations with Canva, Figma, Adobe Creative Cloud, Meta Ads Manager, and Google Ads for pre-flight compliance screening before publication.
- **Continuous Policy Synchronization**:
  - Webhook listeners alerting marketing teams when active guidelines change, with automated impact assessments across previously reviewed campaigns.
