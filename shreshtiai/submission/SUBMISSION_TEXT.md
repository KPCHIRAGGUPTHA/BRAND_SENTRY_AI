# HackCulture submission: GAVS Hackathon, idea round

**Theme:** MSME Finance and Compliance
**Problem:** 3.1 Micro enterprises lose time and profit to compliance paperwork
**Idea title:** ShreshtiAI, an agentic "digital munim" for micro enterprise compliance. Tagline: Check before you file. Get paid on time.

## Short description of the idea

ShreshtiAI is an agentic AI compliance assistant for India's micro enterprises. The owner sends photos of invoices, bills and government notices on WhatsApp or the web. A team of AI agents extracts the data, checks it against GST, income-tax and MSMED Act rules, flags every error and deadline with the exact rule section cited, and produces the corrected invoice, return summary, notice reply or payment reminder for one-tap owner approval, in English, Kannada or Hindi. It is voice-first and runs over WhatsApp on any low-cost Android phone, so it works for owners with low literacy and patchy connectivity. Hours of monthly paperwork become a few minutes of review, and avoidable late fees and penalties disappear.

## Detailed explanation of the idea

*Problem.* 99.3% of India's 9 crore+ Udyam-registered MSMEs are micro enterprises, and most have no accountant. A single-state manufacturing MSME faces 1,450+ compliance obligations a year, costing ₹13–17 lakh (TeamLease RegTech, 2025). Recent changes mean errors can no longer be fixed after filing: the GSTR-3B hard lock (July 2025), the 3-year bar on late returns, and the new Income-tax Act 2025 (from 1 April 2026). Late returns cost ₹50 a day plus 18% interest, and wrong invoices block buyers' input-tax credit. Meanwhile, micro suppliers have ₹20,979 crore stuck in pending delayed-payment claims.

*Solution: five cooperating agents with a human in the loop.*
1. Intake Agent: OCR + LLM extraction of GSTIN, HSN, tax, dates and amounts from photos and PDFs, with a confidence score per field.
2. Rule-Check Agent: hybrid BM25 + vector retrieval over versioned official texts (CGST Act and Rules, CBIC circulars, GSTN advisories, MSMED Act, Income-tax Act 2025 with old-to-new section mapping). Each finding is COMPLIANT, NON-COMPLIANT, OUTDATED (e.g. a tax rate changed under GST 2.0, or an Income-tax 1961 section replaced by the 2025 Act) or NEEDS REVIEW, with the exact section cited. It abstains rather than guesses.
3. Deadline Agent: knows the business's scheme (QRMP, composition or monthly) and sends reminders before the GSTR-1, PMT-06, GSTR-3B and CMP-08 due dates, showing the late fee at stake.
4. Drafting Agent: produces the corrected invoice line using approved wording, return summaries, plain-language explanations and replies to notices, and MSMED 15/45-day payment reminders to buyers who pay late.
5. Orchestrator: plans multi-step goals ("close this quarter") and keeps per-business memory. Anything that files, sends or pays goes to the owner for approval, with an optional CA review queue and a full audit log.

*Why it is different.* Billing apps (Vyapar, myBillBook, Tally) record transactions, and enterprise tools (Clear) target large companies. ShreshtiAI checks before filing and explains why, with citations. It works across GST, income tax and MSME payment law in one place, and it speaks the owner's language on WhatsApp.

*Who benefits.* Shop owner: no avoidable fines, and paid on time. CA: clean, pre-checked files, so one CA can serve far more small clients. Trader association: members stay compliant and credit-ready.

*Built for Bharat.* Voice-first: owners speak and listen in Kannada or Hindi, with no forms to read. It works over WhatsApp on any low-cost Android phone, compresses photos for 2G/3G, queues uploads when offline, and falls back to SMS reminders where there is no data. A trader-association volunteer or the owner's CA can also operate it on the owner's behalf.

*Proof plan.* In the prototype round, ShreshtiAI will be tested head-to-head against a single LLM prompt on a labelled set of about 20 synthetic invoices with known errors, and the method and results will be published. Judges can try it with no sign-up through role-based demo logins (Owner, CA, Association) on a fictional shop, Sri Lakshmi Traders, Birur. Every approval is recorded in a tamper-evident, hash-chained audit log.

*Tech stack.* FastAPI, agent orchestration on Lyzr AI (the hackathon's AI partner, using participant credits) with a LangGraph fallback, PyMuPDF + OCR, ChromaDB + BM25 hybrid retrieval, a React + TypeScript dashboard, a WhatsApp interface, and multilingual output. The citation-grounded retrieval core is adapted from my deployed compliance-RAG system, BrandSentry AI. The first deterministic GST checks (GSTIN checksum, tax type, late fee) are already written and tested in the ShreshtiAI repo.

*Impact and roadmap.* Pilot targets: monthly compliance review under 15 minutes, zero missed due dates, and receivables recovered once they pass 45 days. Phase 2 runs pilots with trader associations. Phase 3 turns a consented, clean compliance history into a credit-readiness profile matched to MUDRA, CGTMSE and GST Sahay invoice financing, which addresses problem 3.2 as well.

*Inspiration.* The Arya Vysya trading tradition of the shreshti and the trusted shop munim, rebuilt as an AI agent for every small trader.

## Supporting links

1. https://github.com/KPCHIRAGGUPTHA/shreshtiai
2. https://github.com/KPCHIRAGGUPTHA/BRAND_SENTRY_AI (engine) · https://brandsentry-web.onrender.com
