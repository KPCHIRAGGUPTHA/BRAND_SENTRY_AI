# Round 3 Report: Claims Audit

Audit of the submitted report (`documents/round3_submission.pdf`) against the code on the
`post-submission-hardening` branch. The submission itself is tagged `round3-submission` (`75a7a72`).

- **REAL:** the code does what the report says.
- **PARTIAL:** something exists, but less than the report says.
- **MISSING:** not implemented.
- **At submission** is the state at the deadline. **Now** is the state after this work.

## Features

| Report claim | At submission | Now | What the code does |
| :--- | :--- | :--- | :--- |
| "Load Sample Marketing Compliance Guidelines" button | MISSING | REAL | `POST /api/guidelines/load-sample` plus a button; no duplicates |
| Quick-start claims 1 to 4 | PARTIAL | REAL | See note 1 |
| Logo clear margin validated from the image | MISSING | PARTIAL | Text only at submission. Pixel margins now measure the nearest non-background content, not the logo. The UI says verdicts come from the claim text |
| Dominant colour extraction | MISSING | REAL | `visual_checks.dominant_colors` |
| Colour contrast check | MISSING | PARTIAL | Measures the lowest WCAG contrast of OCR words; flags no policy breach automatically |
| 8pt minimum font check | MISSING | PARTIAL | Measures smallest word height and an approximate point size (assumes 96 DPI); no pass or fail, because true point size is unknowable from pixels |
| Prohibited stretching or recolouring of the emblem | MISSING | MISSING | Needs a reference logo; see the open list |
| Guideline version snapshots with SHA-256 | REAL | REAL | `policy_versions.content_hash`, one version per content hash |
| Revision diff view | MISSING | PARTIAL | Sentence-level text diff with a Compare button. The report says it diffs section embeddings; it does not |
| Reviewer state machine with mandatory justification | MISSING | REAL | `POST /api/reviews/{id}/transition`, history stored, reviews with contradictions must pass legal. Reviewer names are not authenticated |
| PDF certificate with SHA-256 stamp | PARTIAL | REAL | Was a truncated hash of the input text. Now a full hash of content and verdicts |
| "Cryptographically / digitally signed" certificate | MISSING | MISSING | It is a hash, not a signature. The UI and PDF say so; the report wording is wrong |
| Reviewer sign-offs in the PDF | MISSING | REAL | State history is printed |
| 7 drift categories, severity, rewrites | PARTIAL | REAL | Categories and severity existed, but the UI never showed rewrites |
| Exact identifier validation (`9845-A` vs `4412-K`) | REAL | REAL | |
| Hybrid RRF, k=60 | REAL | REAL | |
| Optional LLM with quote validation | REAL | REAL | `google-generativeai` is not in `requirements.txt`, so Gemini silently falls back to deterministic |
| `/health` returns uptime, component health, build hash | MISSING | PARTIAL | Now returns uptime, readiness and build; no per-component health |
| Rate limiting | MISSING | MISSING | No limiter exists. Not added: it could block judges |
| Tailwind CSS | MISSING | MISSING | Plain CSS. Report wording is wrong |
| PyMuPDF raster parsing of images | MISSING | MISSING | Images use Pillow and Tesseract. PyMuPDF is used for PDFs only |
| SHA-256 embedding cache, 10,000 entries | MISSING | MISSING | Keys are lowercased text; limit is 2,048 entries. Still thread-safe LRU |
| 400-character chunks, 100 overlap | MISSING | MISSING | Actual: 300 words, 40 overlap |
| Uvicorn workers, auto-healing, active memory safeguards | MISSING | MISSING | Single Uvicorn process; Render restarts it |
| Page 6 example: "Get 40% off", "24px margin" return `SUPPORTED` | MISSING | PARTIAL | Those exact words return `INSUFFICIENT_EVIDENCE` (below the similarity threshold). Fuller wording that names the rule works, with limits read from the guideline |
| Recall@1 86.67%, MRR 0.9142 | MISSING | MISSING | See note 2 |
| Blind set "executed once, untouched" | PARTIAL | MISSING | True at submission, no longer: it has been re-run many times and informed decisions |

**Note 1.** At submission the bundled sample had no Section 11 and no `9845-A`, those existed only in the
benchmark corpus. Claim 2 cited an unrelated sentence, and claim 4 could never fire because no guideline
had hedged wording for it. The new bundled guideline adds those sections and **one sentence written so claim 4
has something to detect**: "Software tools may improve team productivity when teams adopt them fully." That
makes the demo work. It does not show drift detection works on arbitrary documents.

**Note 2.** Measured hybrid on the 60-query benchmark: recall@1 79.72%, precision@1 86.67%, MRR 0.9061.
The report's "Recall@1 86.67%" is really precision@1. Dense scores higher than hybrid on recall@1 (84.72%), MRR
(0.9385), and on the holdout verdict accuracy (83.05% vs 81.36%), so the report's claim that hybrid improves
retrieval is not supported by the current results.

## Performance

Reproduce with `python scripts/measure_perf.py`. This measures a local machine, not Render, whose free tier has
far less CPU. The report did not state its conditions, and no script for its numbers exists in the repository.

Environment: Windows AMD64, Python 3.11.16, 16 CPUs.

| Metric | Report | Measured (median) | Worst of 30 |
| :--- | ---: | ---: | ---: |
| Single claim review, warm | 42.8 ms | 32.9 ms | 413.3 ms |
| 10-claim review, warm | 184.5 ms | 120.2 ms | 1144.6 ms |
| 20-page PDF ingest | 1.82 s | 1.28 s (20 chunks) | |
| Cache hit, same claim repeated | 94.2% | 96.7% | |
| Cache hit, all new claims | not reported | 0.0% | |
| Process memory (RSS) | 285 MB | 200 MB (Windows, not the Linux container) | |
| Model load | not reported | 1.48 s | |

The cache hit ratio describes the workload, not the system: it is high only when claims repeat.

## Engine rules that match benchmark-specific phrases

Each rule was disabled alone, then benchmarks and backend tests were run. Baseline: dev 93.33, holdout 81.36, blind 78.12.

| Rule | Dev | Holdout | Blind | Tests | Covered by `guideline_directives.py`? | Outcome |
| :--- | ---: | ---: | ---: | :--- | :--- | :--- |
| Medical phrases (psoriasis, influenza) | 93.33 | 81.36 | 78.12 | Pass | Yes | **Removed** |
| Bare "zero risk" | 93.33 | 81.36 | 78.12 | Pass | Yes | **Removed** |
| Return-window exception | 93.33 | 81.36 | 78.12 | Pass | Yes | **Removed** |
| "No promotional campaign" | 93.33 | 81.36 | 78.12 | Pass | Yes | **Removed** |
| Policy-restatement phrases | 93.33 | 81.36 | 78.12 | Pass | Yes | **Removed** |
| Literal `20px` margin | 93.33 | 80.51 | 75.00 | Pass | No | **Generalised** to read the limit |
| Literal `50%` cap | 93.33 | 80.51 | 75.00 | Pass | No | **Generalised** to read the limit |
| `doc-finance` document id | 93.33 | 80.51 | 75.00 | Pass | No | **Generalised**, id removed |
| Unattached evidence (internal ledger, offline server) | 93.33 | 79.66 | 78.12 | Pass | No | Kept |
| Self-reported approval (marketing VP orally) | 93.33 | 80.51 | 78.12 | 1 fails | No | Kept |
| Compound "100% security", "chronic" | 93.33 | 78.81 | 78.12 | Pass | No | Kept |
| Temporal (five years ago, in a 2016) | 91.67 | 79.66 | 78.12 | 1 fails | No | Kept |
| "semantic similarity score guarantees" | 91.67 | 81.36 | 78.12 | Pass | No | Kept |
| Substantiation phrases | 88.33 | 81.36 | 78.12 | Pass | No | Kept |
| Percentage performance | 93.33 | 77.97 | 78.12 | 1 fails | No | Kept |
| Absolute security and environment | 90.00 | 77.97 | 75.00 | 1 fails | No | Kept |
| Superlatives (unrivaled superiority) | 93.33 | 80.51 | 78.12 | Pass | No | Kept |
| Bare "carbon neutral" | 91.67 | 81.36 | 78.12 | 1 fails | No | Kept |
| Double-negative compliance | 93.33 | 80.51 | 78.12 | Pass | No | Kept |
| `9845-A` cross-domain (tea bags, trading portal) | 93.33 | 78.81 | 78.12 | Pass | No | Kept |
| Internal operations (warehouse, cafeteria) | 93.33 | 78.81 | 78.12 | Pass | No | Kept |
| Constraint restatement | 91.67 | 81.36 | 78.12 | 1 fails | No | Kept |

Benchmarks after each of the 8 removals and generalisations stayed at 93.33 / 81.36 / 78.12, with false approvals at
0 / 1 / 1. **Removing a rule without a score change shows those benchmarks do not depend on it, not that the
rule was never useful.** Smaller phrase lists were not measured individually: `_is_compliant_disclaimer`,
`_DOMAIN_SYNONYMS`, and the scoring boosts for "fees" and "exceptional result". Those phrase rules still mean the
holdout and blind scores overstate accuracy on documents the engine has never seen.
