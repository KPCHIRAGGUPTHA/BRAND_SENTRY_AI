"""
Independent Blind Evaluation Runner for BrandSentry AI.
Evaluates the unseen 32-case blind benchmark set once without tuning against it.
"""
import os
import sys
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.evaluation.evaluate_retrieval import load_corpus
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.vector_store import VectorStoreService
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService
from backend.app.services.verdict_engine import (
    verdict_engine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
)

BENCHMARK_PATH = Path("backend/evaluation/datasets/blind_evaluation_benchmark.jsonl")
RESULTS_PATH = Path("backend/evaluation/results/blind_evaluation_results.json")


def load_dataset(path: str) -> List[Dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def compute_metrics(predictions: List[Dict[str, Any]], mode_key: str) -> Dict[str, Any]:
    labels = [VERDICT_SUPPORTED, VERDICT_CONTRADICTED, VERDICT_INSUFFICIENT]
    total = len(predictions)
    correct = sum(1 for p in predictions if p[mode_key] == p["expected"])
    accuracy = correct / total if total > 0 else 0.0

    conf = {e: {pred: 0 for pred in labels} for e in labels}
    for p in predictions:
        exp = p["expected"]
        pred = p[mode_key]
        if exp in conf and pred in conf[exp]:
            conf[exp][pred] += 1

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

    fp_support = conf[VERDICT_CONTRADICTED][VERDICT_SUPPORTED] + conf[VERDICT_INSUFFICIENT][VERDICT_SUPPORTED]
    fp_contradiction = conf[VERDICT_SUPPORTED][VERDICT_CONTRADICTED] + conf[VERDICT_INSUFFICIENT][VERDICT_CONTRADICTED]

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
            "accuracy": round(stat["correct"] / stat["total"], 4),
        }

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "confusion_matrix": conf,
        "per_class": per_class,
        "false_positive_support": fp_support,
        "false_positive_support_rate": round(fp_support / total, 4) if total > 0 else 0.0,
        "false_positive_contradiction": fp_contradiction,
        "false_positive_contradiction_rate": round(fp_contradiction / total, 4) if total > 0 else 0.0,
        "category_accuracy": category_accuracy,
    }


def evaluate_blind():
    corpus = load_corpus()
    blind_dataset = load_dataset(str(BENCHMARK_PATH))
    print(f"Loaded {len(blind_dataset)} blind benchmark cases.")

    temp_dir = tempfile.mkdtemp(prefix="blind_eval_")
    chroma_dir = os.path.join(temp_dir, "chroma")
    bm25_dir = os.path.join(temp_dir, "bm25")

    try:
        vstore = VectorStoreService(persist_dir=chroma_dir, collection_name="blind_eval_chunks")
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

        predictions = []
        for item in blind_dataset:
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
                "dense_rule": d_obj.deterministic_rule_fired,
                "hybrid_rule": h_obj.deterministic_rule_fired,
                "hybrid_explanation": h_obj.explanation,
                "hybrid_evidence": [e.quote for e in h_obj.evidence],
            })

        dense_metrics = compute_metrics(predictions, "dense_pred")
        hybrid_metrics = compute_metrics(predictions, "hybrid_pred")

        hybrid_failures = [p for p in predictions if p["hybrid_pred"] != p["expected"]]

        output = {
            "dataset_name": "Blind Final Evaluation Set (Stage 3.5)",
            "total_cases": len(blind_dataset),
            "dense_metrics": dense_metrics,
            "hybrid_metrics": hybrid_metrics,
            "hybrid_failures": hybrid_failures,
            "predictions": predictions,
        }

        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        print("\n" + "=" * 55)
        print(f"BLIND FINAL EVALUATION RESULTS (N={len(blind_dataset)})")
        print("=" * 55)
        print(f"Dense  Accuracy: {dense_metrics['accuracy']:.4f} ({dense_metrics['correct']}/{dense_metrics['total']})")
        print(f"Hybrid Accuracy: {hybrid_metrics['accuracy']:.4f} ({hybrid_metrics['correct']}/{hybrid_metrics['total']})")
        print(f"False-Positive Support (Hybrid): {hybrid_metrics['false_positive_support']} ({hybrid_metrics['false_positive_support_rate']*100:.2f}%)")
        print(f"False-Positive Contradiction (Hybrid): {hybrid_metrics['false_positive_contradiction']} ({hybrid_metrics['false_positive_contradiction_rate']*100:.2f}%)")

        print("\nConfusion Matrix (Hybrid):")
        print(f"  {'':22s} | {'SUP':>6s} | {'CON':>6s} | {'INS':>6s}")
        for row in [VERDICT_SUPPORTED, VERDICT_CONTRADICTED, VERDICT_INSUFFICIENT]:
            print(f"  {row:22s} | {hybrid_metrics['confusion_matrix'][row][VERDICT_SUPPORTED]:6d} | {hybrid_metrics['confusion_matrix'][row][VERDICT_CONTRADICTED]:6d} | {hybrid_metrics['confusion_matrix'][row][VERDICT_INSUFFICIENT]:6d}")

        print("\nPer-class Metrics (Hybrid):")
        for k, v in hybrid_metrics["per_class"].items():
            print(f"  {k:22s}: Prec={v['precision']:.4f}, Rec={v['recall']:.4f}, F1={v['f1']:.4f}")

        print("\nCategory Breakdown (Hybrid):")
        for cat, stat in hybrid_metrics["category_accuracy"].items():
            print(f"  {cat:32s}: {stat['correct']}/{stat['total']} ({stat['accuracy']*100:.1f}%)")

        if hybrid_failures:
            print(f"\nFailures ({len(hybrid_failures)}):")
            for f in hybrid_failures:
                print(f"  - [{f['id']}] ({f['category']}) expected={f['expected']} pred={f['hybrid_pred']}")
                print(f"    Claim: '{f['query']}'")
                print(f"    Expl: '{f['hybrid_explanation'][:100]}...'")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    evaluate_blind()
