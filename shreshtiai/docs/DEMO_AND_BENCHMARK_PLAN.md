# Demo and benchmark plan (prototype round)

## Demo, with no sign-up

A fictional business, **Sri Lakshmi Traders, Birur** (Karnataka, QRMP filer). All data is synthetic.

| Role login | Opens on | Shows |
| --- | --- | --- |
| Shop owner | Inbox | Upload invoices, see cited findings and corrected lines, approve with one tap |
| Chartered accountant | Review queue | Only NEEDS REVIEW items; a pre-checked quarter summary |
| Trader association | Members dashboard | Upcoming deadlines and compliance status across member shops |

**Five demo steps**

1. Upload 10 sample invoices, some correct and some with planted errors.
2. A cited error report shows the section and the corrected line, in English and Kannada.
3. A deadline calendar shows the next GSTR-1, PMT-06 and GSTR-3B dates and the fee if missed.
4. A sample GST notice gets a plain-language summary and a draft reply.
5. The receivables view flags a buyer past 45 days and drafts an MSMED reminder.

## Head-to-head benchmark

**Question:** does the agent pipeline catch more real errors than one well-written LLM prompt, without more false alarms?

| Item | Plan |
| --- | --- |
| Dataset | About 20 synthetic invoices; each labelled with its true errors (or none) |
| Error types | Invalid GSTIN, wrong tax type (IGST vs CGST + SGST), unequal CGST/SGST, wrong HSN rate, rate made OUTDATED by GST 2.0, missing place of supply, arithmetic error, 1961-Act section cited after 1 April 2026 |
| Systems | (A) ShreshtiAI pipeline; (B) a single prompt with the invoice and rule texts, same model |
| Metrics | Errors caught / total errors, false alarms, correct citations / citations |
| Published | Dataset, labels, prompt for (B), scripts and results in `benchmark/` |

The numbers will be reported as measured, with the sample size stated.

## Audit

Every approval record stores the hash of the previous record (SHA-256), so any later edit breaks the chain and shows up on verification.
