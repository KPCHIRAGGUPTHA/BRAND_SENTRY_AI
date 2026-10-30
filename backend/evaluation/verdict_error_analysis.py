"""
Verdict Error Analysis and Paired Statistical Comparison for BrandSentry AI.
Compares Dense vs Hybrid retrieval-grounded verdict predictions across all 60 benchmark examples.
Calculates:
- 2x2 Contingency Matrix (McNemar's format):
  1. Dense Correct / Hybrid Correct
  2. Dense Correct / Hybrid Incorrect
  3. Dense Incorrect / Hybrid Correct
  4. Both Incorrect
- Paired statistical test (McNemar's test with continuity correction & exact binomial test)
- Itemized failure log with root-cause categorization.
"""
import os
import sys
import json
import math
import shutil
import tempfile
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.evaluation.evaluate_retrieval import load_corpus, load_benchmark
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.vector_store import VectorStoreService
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService
from backend.app.services.verdict_engine import verdict_engine


def run_verdict_analysis():
    corpus = load_corpus()
    benchmark = load_benchmark()
    temp_dir = tempfile.mkdtemp(prefix="brandsentry_verdict_")
    try:
        chroma_dir = os.path.join(temp_dir, "chroma")
        bm25_dir = os.path.join(temp_dir, "bm25")

        vstore = VectorStoreService(persist_dir=chroma_dir, collection_name="verdict_analysis_chunks")
        bm25_svc = BM25RetrieverService(persist_dir=bm25_dir)
        chunk_texts = [c.text for c in corpus]
        embs = embedding_service.generate_embeddings(chunk_texts)
        vstore.add_chunks(corpus, embs)
        bm25_svc.add_chunks(corpus)

        retriever = HybridRetrieverService(
            vector_store=vstore,
            bm25_service=bm25_svc,
            embeddings=embedding_service,
            smoothing_k=60,
        )

        both_correct = []
        dense_only_correct = []
        hybrid_only_correct = []
        both_incorrect = []

        all_predictions = []

        for item in benchmark:
            qid = item["id"]
            query = item["query"]
            cat = item["category"]
            scope = item.get("document_scope")
            expected_verdict = item["expected_verdict"]
            expected_chunks = item.get("expected_chunk_ids", [])

            # Dense retrieval & classification
            d_passages = retriever.search(query=query, document_id=scope, top_k=5, mode="dense")
            d_verdict_obj = verdict_engine.classify(claim_id=qid, claim_text=query, retrieved_passages=d_passages)
            d_pred = d_verdict_obj.verdict
            d_correct = (d_pred == expected_verdict)

            # Hybrid retrieval & classification
            h_passages = retriever.search(query=query, document_id=scope, top_k=5, mode="hybrid")
            h_verdict_obj = verdict_engine.classify(claim_id=qid, claim_text=query, retrieved_passages=h_passages)
            h_pred = h_verdict_obj.verdict
            h_correct = (h_pred == expected_verdict)

            record = {
                "id": qid,
                "category": cat,
                "query": query,
                "expected": expected_verdict,
                "dense_pred": d_pred,
                "dense_correct": d_correct,
                "dense_rule": d_verdict_obj.deterministic_rule_fired,
                "hybrid_pred": h_pred,
                "hybrid_correct": h_correct,
                "hybrid_rule": h_verdict_obj.deterministic_rule_fired,
                "expected_chunks": expected_chunks,
                "dense_chunks": [p["chunk_id"] for p in d_passages],
                "hybrid_chunks": [p["chunk_id"] for p in h_passages],
            }
            all_predictions.append(record)

            if d_correct and h_correct:
                both_correct.append(record)
            elif d_correct and not h_correct:
                dense_only_correct.append(record)
            elif not d_correct and h_correct:
                hybrid_only_correct.append(record)
            else:
                both_incorrect.append(record)

        # -----------------------------------------------------------------
        # Contingency Matrix & Statistical Testing
        # -----------------------------------------------------------------
        n_both_correct = len(both_correct)
        n_dense_only = len(dense_only_correct)
        n_hybrid_only = len(hybrid_only_correct)
        n_both_incorrect = len(both_incorrect)
        total = len(benchmark)

        dense_acc = (n_both_correct + n_dense_only) / total
        hybrid_acc = (n_both_correct + n_hybrid_only) / total

        # McNemar's Chi-squared test with Edwards continuity correction:
        # chi2 = (|b - c| - 1)^2 / (b + c)  where b = n_dense_only, c = n_hybrid_only
        b = n_dense_only
        c = n_hybrid_only
        discordant = b + c
        if discordant > 0:
            mcnemar_stat = (abs(b - c) - 1.0) ** 2 / discordant if abs(b - c) > 0 else 0.0
            # Exact two-tailed binomial test for small sample
            # P(X >= max(b, c)) under Binomial(n=b+c, p=0.5)
            k_val = max(b, c)
            exact_p = 2.0 * sum(math.comb(discordant, i) * (0.5 ** discordant) for i in range(k_val, discordant + 1))
            exact_p = min(1.0, exact_p)
        else:
            mcnemar_stat = 0.0
            exact_p = 1.0

        print("=" * 80)
        print("STAGE 2 VERDICT ERROR ANALYSIS & PAIRED STATISTICAL COMPARISON")
        print("=" * 80)
        print(f"Total Queries Evaluated: {total}")
        print(f"Dense Verdict Accuracy : {dense_acc:.2%} ({n_both_correct + n_dense_only}/{total})")
        print(f"Hybrid Verdict Accuracy: {hybrid_acc:.2%} ({n_both_correct + n_hybrid_only}/{total})")
        print("\n2x2 PAIRED CONTINGENCY MATRIX:")
        print(f"  • Both Correct                     : {n_both_correct:<2} ({n_both_correct/total:.1%})")
        print(f"  • Dense Correct / Hybrid Incorrect : {n_dense_only:<2} ({n_dense_only/total:.1%})")
        print(f"  • Dense Incorrect / Hybrid Correct : {n_hybrid_only:<2} ({n_hybrid_only/total:.1%})")
        print(f"  • Both Incorrect                   : {n_both_incorrect:<2} ({n_both_incorrect/total:.1%})")
        print(f"\nPaired Statistical Analysis (McNemar Discordant Pairs = {discordant}):")
        print(f"  • McNemar's Statistic (corrected)  : {mcnemar_stat:.4f}")
        print(f"  • Exact Binomial Two-Tailed p-value: {exact_p:.4f}")
        if exact_p > 0.05:
            print("  • Interpretation: No statistically significant classification divergence between Dense and Hybrid (p > 0.05).")
        else:
            print("  • Interpretation: Statistically significant divergence observed (p <= 0.05).")

        # -----------------------------------------------------------------
        # Categorized Failure Breakdown
        # -----------------------------------------------------------------
        print("\n" + "=" * 80)
        print("ITEMIZED FAILURE LOG & ROOT-CAUSE CATEGORIZATION")
        print("=" * 80)

        def categorize_failure(rec: Dict[str, Any], mode_name: str) -> str:
            pred = rec[f"{mode_name}_pred"]
            exp = rec["expected"]
            chunks = rec[f"{mode_name}_chunks"]
            exp_chunks = set(rec["expected_chunks"])

            # Check if expected passage was retrieved in top 3
            retrieved_expected = any(c in exp_chunks for c in chunks[:3]) if exp_chunks else True

            if not retrieved_expected:
                return "RETRIEVAL_FAILURE (Target guideline chunk omitted from top passages)"
            if exp == "SUPPORTED" and pred == "INSUFFICIENT_EVIDENCE":
                return "UNDER_GROUNDING / CONSERVATIVE_POLICY (Claim contains partial terms not literally proven in top passage)"
            if exp == "CONTRADICTED" and pred == "INSUFFICIENT_EVIDENCE":
                return "POLICY_GAP / WEAK_CONTRADICTION_TRIGGER (Violation nuance requires specialized domain rule)"
            if exp == "SUPPORTED" and pred == "CONTRADICTED":
                return "FALSE_POSITIVE_CONTRADICTION (Exception/negation misclassified as policy violation)"
            if exp == "CONTRADICTED" and pred == "SUPPORTED":
                return "FALSE_POSITIVE_SUPPORT (Prohibited language bypassed grounding check)"
            return "CLASSIFICATION_DISCREPANCY"

        # 1. Dense Only Correct
        print(f"\n[Group 1] Dense Correct / Hybrid Incorrect ({len(dense_only_correct)} items):")
        for r in dense_only_correct:
            reason = categorize_failure(r, "hybrid")
            print(f"  - [{r['id']}] ({r['category']}): '{r['query']}'")
            print(f"    Expected: {r['expected']} | Dense: {r['dense_pred']} | Hybrid: {r['hybrid_pred']}")
            print(f"    Root Cause: {reason}")
            print(f"    Retrieved: Dense={r['dense_chunks'][:2]} | Hybrid={r['hybrid_chunks'][:2]}")

        # 2. Hybrid Only Correct
        print(f"\n[Group 2] Dense Incorrect / Hybrid Correct ({len(hybrid_only_correct)} items):")
        for r in hybrid_only_correct:
            reason = categorize_failure(r, "dense")
            print(f"  - [{r['id']}] ({r['category']}): '{r['query']}'")
            print(f"    Expected: {r['expected']} | Dense: {r['dense_pred']} | Hybrid: {r['hybrid_pred']}")
            print(f"    Root Cause: {reason}")
            print(f"    Retrieved: Dense={r['dense_chunks'][:2]} | Hybrid={r['hybrid_chunks'][:2]}")

        # 3. Both Incorrect
        print(f"\n[Group 3] Both Incorrect ({len(both_incorrect)} items):")
        cat_counts: Dict[str, int] = {}
        reason_counts: Dict[str, int] = {}
        for r in both_incorrect:
            reason = categorize_failure(r, "hybrid")
            cat_counts[r['category']] = cat_counts.get(r['category'], 0) + 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            print(f"  - [{r['id']}] ({r['category']}): '{r['query']}'")
            print(f"    Expected: {r['expected']} | Actual (Dense={r['dense_pred']}, Hybrid={r['hybrid_pred']})")
            print(f"    Root Cause: {reason}")

        print("\nFAILURE REASON SUMMARY (Both Incorrect):")
        for reason, cnt in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {cnt:2d} instances: {reason}")

        print("\nCATEGORY FAILURE SUMMARY (Both Incorrect):")
        for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {cnt:2d} instances: {cat}")

        # Save machine-readable output
        out_path = os.path.join(PROJECT_ROOT, "backend", "evaluation", "results", "verdict_error_analysis.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "dense_accuracy": dense_acc,
                "hybrid_accuracy": hybrid_acc,
                "both_correct_count": n_both_correct,
                "dense_only_correct_count": n_dense_only,
                "hybrid_only_correct_count": n_hybrid_only,
                "both_incorrect_count": n_both_incorrect,
                "mcnemar_stat": mcnemar_stat,
                "exact_p_value": exact_p,
                "dense_only_items": dense_only_correct,
                "hybrid_only_items": hybrid_only_correct,
                "both_incorrect_items": both_incorrect,
                "all_predictions": all_predictions,
            }, f, indent=2)
        print(f"\nSaved detailed analysis to {out_path}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_verdict_analysis()

