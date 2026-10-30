"""
Independent Holdout Evaluation and Audit Runner for BrandSentry AI.
Evaluates the frozen original 60-query benchmark and the new 118-query adversarial holdout.
Computes:
- Overall accuracy (Dense & Hybrid)
- Precision, Recall, and F1 for SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE
- False-positive support count & False-positive contradiction count
- 3x3 Confusion matrix
- Accuracy broken down by category
- Itemized failure log with root causes:
  - SEMANTIC_DRIFT
  - INCOMPLETE_EVIDENCE
  - POLICY_NUANCE
  - NEGATION_OR_DOUBLE_NEGATIVE_ERROR
  - FALSE_POSITIVE_CONTRADICTION
  - FALSE_POSITIVE_SUPPORT
  - RETRIEVAL_DISPLACEMENT
  - AMBIGUOUS_CLASSIFICATION
"""

import os
import sys
import json
import math
import shutil
import tempfile
from typing import List, Dict, Any, Tuple
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.evaluation.evaluate_retrieval import load_corpus
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.vector_store import VectorStoreService
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService
from backend.app.services.verdict_engine import verdict_engine


def load_dataset(path: str) -> List[Dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def compute_metrics(predictions: List[Dict[str, Any]], mode_key: str) -> Dict[str, Any]:
    labels = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
    total = len(predictions)
    correct = sum(1 for p in predictions if p[mode_key] == p["expected"])
    accuracy = correct / total if total > 0 else 0.0

    # Confusion matrix: conf[expected][predicted]
    conf = {e: {pred: 0 for pred in labels} for e in labels}
    for p in predictions:
        exp = p["expected"]
        pred = p[mode_key]
        if exp in conf and pred in conf[exp]:
            conf[exp][pred] += 1

    # Class-level precision, recall, F1
    per_class = {}
    for lbl in labels:
        tp = conf[lbl][lbl]
        fp = sum(conf[other][lbl] for other in labels if other != lbl)
        fn = sum(conf[lbl][other] for other in labels if other != lbl)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[lbl] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    # False-positive support: predicted SUPPORTED when expected CONTRADICTED or INSUFFICIENT
    fp_support = conf["CONTRADICTED"]["SUPPORTED"] + conf["INSUFFICIENT_EVIDENCE"]["SUPPORTED"]
    # False-positive contradiction: predicted CONTRADICTED when expected SUPPORTED or INSUFFICIENT
    fp_contradiction = conf["SUPPORTED"]["CONTRADICTED"] + conf["INSUFFICIENT_EVIDENCE"]["CONTRADICTED"]

    # Category breakdown
    cat_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    for p in predictions:
        cat = p["category"]
        cat_stats[cat]["total"] += 1
        if p[mode_key] == p["expected"]:
            cat_stats[cat]["correct"] += 1

    category_accuracy = {}
    for cat, stat in sorted(cat_stats.items()):
        category_accuracy[cat] = {
            "total": stat["total"],
            "correct": stat["correct"],
            "accuracy": round(stat["correct"] / stat["total"], 4) if stat["total"] > 0 else 0.0
        }

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "confusion_matrix": conf,
        "per_class": per_class,
        "false_positive_support": fp_support,
        "false_positive_contradiction": fp_contradiction,
        "category_accuracy": category_accuracy,
    }


def diagnose_failure(record: Dict[str, Any], mode_key: str) -> Tuple[str, str]:
    """Diagnoses root cause of a verdict misclassification."""
    expected = record["expected"]
    predicted = record[mode_key]
    query = record["query"].lower()
    retrieved = record[f"{mode_key[:1]}_chunks"]

    if expected == "SUPPORTED" and predicted == "CONTRADICTED":
        if any(neg in query for neg in ["not", "never", "no", "without"]):
            return "NEGATION_OR_DOUBLE_NEGATIVE_ERROR", "Negation or double negative in compliant disclaimer improperly triggered contradiction."
        return "FALSE_POSITIVE_CONTRADICTION", "Engine fired policy prohibition on claim that adhered to guidelines."

    if expected == "CONTRADICTED" and predicted == "SUPPORTED":
        return "FALSE_POSITIVE_SUPPORT", "Engine affirmed compliance for a statement containing prohibited guarantees or unbacked claims."

    if expected == "INSUFFICIENT_EVIDENCE" and predicted == "SUPPORTED":
        return "FALSE_POSITIVE_SUPPORT", "Self-attestation or out-of-scope passage improperly treated as sufficient documentary evidence."

    if expected == "INSUFFICIENT_EVIDENCE" and predicted == "CONTRADICTED":
        return "FALSE_POSITIVE_CONTRADICTION", "Engine asserted definitive contradiction where evidence was absent or inconclusive."

    if expected in ("SUPPORTED", "CONTRADICTED") and predicted == "INSUFFICIENT_EVIDENCE":
        if not retrieved or len(retrieved) == 0:
            return "RETRIEVAL_DISPLACEMENT", "No passages were retrieved in top-K candidate pool."
        return "POLICY_NUANCE", "Candidate passages were retrieved but policy rule/conformance logic was not triggered."

    return "AMBIGUOUS_CLASSIFICATION", "Classification diverged due to ambiguous evidence alignment."


def run_evaluation():
    corpus = load_corpus()
    dev_path = os.path.join(PROJECT_ROOT, "backend", "evaluation", "datasets", "retrieval_benchmark.jsonl")
    holdout_path = os.path.join(PROJECT_ROOT, "backend", "evaluation", "datasets", "independent_holdout_benchmark.jsonl")

    dev_data = load_dataset(dev_path)
    holdout_data = load_dataset(holdout_path)

    temp_dir = tempfile.mkdtemp(prefix="brandsentry_eval_")
    try:
        chroma_dir = os.path.join(temp_dir, "chroma")
        bm25_dir = os.path.join(temp_dir, "bm25")

        vstore = VectorStoreService(persist_dir=chroma_dir, collection_name="holdout_eval_chunks")
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

        def eval_set(dataset: List[Dict[str, Any]], name: str):
            predictions = []
            for item in dataset:
                qid = item["id"]
                query = item["query"]
                cat = item["category"]
                scope = item.get("document_scope")
                expected = item["expected_verdict"]

                d_passages = retriever.search(query=query, document_id=scope, top_k=5, mode="dense")
                d_obj = verdict_engine.classify(claim_id=qid, claim_text=query, retrieved_passages=d_passages)
                d_pred = d_obj.verdict

                h_passages = retriever.search(query=query, document_id=scope, top_k=5, mode="hybrid")
                h_obj = verdict_engine.classify(claim_id=qid, claim_text=query, retrieved_passages=h_passages)
                h_pred = h_obj.verdict

                predictions.append({
                    "id": qid,
                    "query": query,
                    "category": cat,
                    "document_scope": scope,
                    "expected": expected,
                    "dense_pred": d_pred,
                    "hybrid_pred": h_pred,
                    "d_chunks": [p.get("chunk_id", "") for p in d_passages],
                    "h_chunks": [p.get("chunk_id", "") for p in h_passages],
                    "dense_rule": d_obj.deterministic_rule_fired,
                    "hybrid_rule": h_obj.deterministic_rule_fired,
                    "hybrid_evidence": [e.quote for e in h_obj.evidence],
                    "notes": item.get("notes", ""),
                })

            dense_metrics = compute_metrics(predictions, "dense_pred")
            hybrid_metrics = compute_metrics(predictions, "hybrid_pred")

            # Collect failures
            hybrid_failures = []
            for p in predictions:
                if p["hybrid_pred"] != p["expected"]:
                    cause, expl = diagnose_failure(p, "hybrid_pred")
                    p_fail = dict(p)
                    p_fail["root_cause"] = cause
                    p_fail["diagnosis"] = expl
                    hybrid_failures.append(p_fail)

            dense_failures = []
            for p in predictions:
                if p["dense_pred"] != p["expected"]:
                    cause, expl = diagnose_failure(p, "dense_pred")
                    p_fail = dict(p)
                    p_fail["root_cause"] = cause
                    p_fail["diagnosis"] = expl
                    dense_failures.append(p_fail)

            return {
                "dataset_name": name,
                "count": len(dataset),
                "dense_metrics": dense_metrics,
                "hybrid_metrics": hybrid_metrics,
                "hybrid_failures": hybrid_failures,
                "dense_failures": dense_failures,
                "all_predictions": predictions,
            }

        print("Evaluating Frozen Development Benchmark (60 queries)...")
        dev_results = eval_set(dev_data, "Frozen Development Set (retrieval_benchmark.jsonl)")

        print("Evaluating Independent Adversarial Holdout (118 queries)...")
        holdout_results = eval_set(holdout_data, "Independent Adversarial Holdout (independent_holdout_benchmark.jsonl)")

        out_dir = os.path.join(PROJECT_ROOT, "backend", "evaluation", "results")
        os.makedirs(out_dir, exist_ok=True)
        report_path = os.path.join(out_dir, "independent_holdout_evaluation.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "development_set": dev_results,
                "holdout_set": holdout_results,
            }, f, indent=2)

        print(f"\nResults successfully written to {report_path}")

        # Summary printout
        print("\n" + "=" * 80)
        print("INDEPENDENT HOLDOUT EVALUATION SUMMARY")
        print("=" * 80)
        print(f"Frozen Dev Set (N=60):")
        print(f"  Dense Accuracy : {dev_results['dense_metrics']['accuracy']*100:.2f}% ({dev_results['dense_metrics']['correct']}/60)")
        print(f"  Hybrid Accuracy: {dev_results['hybrid_metrics']['accuracy']*100:.2f}% ({dev_results['hybrid_metrics']['correct']}/60)")

        print(f"\nIndependent Holdout (N=118):")
        print(f"  Dense Accuracy : {holdout_results['dense_metrics']['accuracy']*100:.2f}% ({holdout_results['dense_metrics']['correct']}/118)")
        print(f"  Hybrid Accuracy: {holdout_results['hybrid_metrics']['accuracy']*100:.2f}% ({holdout_results['hybrid_metrics']['correct']}/118)")
        print(f"  Hybrid FP Support: {holdout_results['hybrid_metrics']['false_positive_support']}")
        print(f"  Hybrid FP Contradiction: {holdout_results['hybrid_metrics']['false_positive_contradiction']}")

        print("\nHoldout Class-Level Metrics (Hybrid):")
        for cls_name, m in holdout_results['hybrid_metrics']['per_class'].items():
            print(f"  {cls_name:22s} | Prec: {m['precision']:.4f} | Rec: {m['recall']:.4f} | F1: {m['f1']:.4f} (TP={m['tp']}, FP={m['fp']}, FN={m['fn']})")

        print("\nHoldout Confusion Matrix (Hybrid) [Expected rows x Predicted cols]:")
        cm = holdout_results['hybrid_metrics']['confusion_matrix']
        print(f"  {'':22s} | {'SUP':>6s} | {'CON':>6s} | {'INS':>6s}")
        for row in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]:
            print(f"  {row:22s} | {cm[row]['SUPPORTED']:6d} | {cm[row]['CONTRADICTED']:6d} | {cm[row]['INSUFFICIENT_EVIDENCE']:6d}")

        print(f"\nHybrid Failure Count: {len(holdout_results['hybrid_failures'])}")
        for f in holdout_results['hybrid_failures']:
            print(f"  - [{f['id']}] ({f['category']}) expected={f['expected']} pred={f['hybrid_pred']} | cause={f['root_cause']}")
            print(f"    Claim: '{f['query']}'")
            print(f"    Note: {f['notes']}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_evaluation()

