# Reusing the BrandSentry AI engine

ShreshtiAI's rule-check agent is built on the retrieval and verdict engine of [BrandSentry AI](https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI), a deployed brand-compliance reviewer. The domain changes from marketing claims to invoices and tax rules. The engine itself stays.

## Kept as is

| BrandSentry file | Role in ShreshtiAI |
| --- | --- |
| `backend/app/retrieval/` (BM25, vector store, hybrid retriever, reranker, embeddings) | Retrieval over the tax-rule knowledge base |
| `backend/app/services/document_registry.py` | Versioned rule sources ("CGST Rules as of …") |
| `backend/app/services/chunking.py`, `extraction.py` | Ingesting acts, circulars and notices |
| `backend/app/services/ocr_service.py` | Reading invoice and notice photos |
| `backend/app/services/audit_service.py` | Audit log, to be extended with hash chaining |
| `backend/evaluation/` | Benchmark harness for the head-to-head test |

## Adapted

| BrandSentry file | Change |
| --- | --- |
| `services/verdict_engine.py` | Verdicts renamed to COMPLIANT / NON_COMPLIANT / OUTDATED / NEEDS_REVIEW; the marketing "universal risk" rules replaced by GST checks from `shreshti/rules/` |
| `services/claim_extractor.py` | Replaced for invoices by an invoice parser that turns each extracted field into a checkable claim |
| `services/semantic_drift.py` | Bypassed for invoices; kept for checking notice replies |
| `resources/` | Brand guideline replaced by tax-rule texts |
| `core/config.py` | Default model updated (the configured `gemini-1.5-flash` is retired) |
| Frontend `ClaimReview.tsx`, `GuidelineExplorer.tsx` | Invoice Check and Rule Library views; a new Deadlines view |

## New

| File | Status |
| --- | --- |
| `shreshti/rules/gstin.py` | Done, tested |
| `shreshti/rules/tax_type.py` | Done, tested |
| `shreshti/rules/late_fee.py` | Done, tested |
| HSN rate table + checker | Prototype round |
| Invoice parser (OCR → JSON with confidence) | Prototype round |
| Deadline agent, drafting agent, orchestrator, approval queue | Prototype round |
| API routes `api/invoices.py`, `api/deadlines.py` | Prototype round |
