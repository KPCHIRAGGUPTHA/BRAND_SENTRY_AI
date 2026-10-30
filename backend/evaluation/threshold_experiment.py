"""
Reproducible Threshold Calibration Experiment for BrandSentry AI.
Evaluates candidate similarity thresholds against the 60-item benchmark dataset.
Measures:
- Supported precision
- Contradicted precision
- False approval rate
- Insufficient evidence rate
- Evidence retrieval quality
"""
import os
import sys
import json
import tempfile
import shutil
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.services.chunking import GuidelineChunk
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.vector_store import VectorStoreService
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService
from backend.app.services.verdict_engine import (
    VerdictEngine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
)

DATASETS_DIR = os.path.join(os.path.dirname(__file__), "datasets")
CORPUS_PATH = os.path.join(DATASETS_DIR, "evaluation_guidelines_corpus.json")
BENCHMARK_PATH = os.path.join(DATASETS_DIR, "retrieval_benchmark.jsonl")


def run_experiment():
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        corpus_data = json.load(f)

    chunks = []
    for d in corpus_data:
        text = d["text"]
        chunks.append(
            GuidelineChunk(
                chunk_id=d["chunk_id"],
                document_id=d["document_id"],
                source_filename=d["source_filename"],
                page_number=d.get("page_number", 1),
                chunk_index=d.get("chunk_index", 0),
                text=text,
                word_count=len(text.split()),
                char_count=len(text),
            )
        )

    temp_dir = tempfile.mkdtemp()
    try:
        chroma_dir = os.path.join(temp_dir, "chroma")
        bm25_dir = os.path.join(temp_dir, "bm25")

        test_vector_store = VectorStoreService(
            persist_dir=chroma_dir,
            collection_name="eval_threshold_chunks",
        )
        test_bm25 = BM25RetrieverService(persist_dir=bm25_dir)

        chunk_texts = [c.text for c in chunks]
        embeddings = embedding_service.generate_embeddings(chunk_texts)
        test_vector_store.add_chunks(chunks, embeddings)
        test_bm25.add_chunks(chunks)

        retriever = HybridRetrieverService(
            vector_store=test_vector_store,
            bm25_service=test_bm25,
            embeddings=embedding_service,
            smoothing_k=60,
        )

        benchmark_items = []
        with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    benchmark_items.append(json.loads(line))

        # Retrieve candidate passages for all queries first
        query_results = []
        for item in benchmark_items:
            scope = item.get("document_scope")
            results = retriever.search(
                query=item["query"],
                document_id=scope,
                top_k=5,
                mode="hybrid",
            )
            query_results.append((item, results))

        candidate_thresholds = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
        metrics = []

        print("\n" + "="*80)
        print("THRESHOLD CALIBRATION EXPERIMENT RESULTS (N=60 Benchmark Items)")
        print("="*80)

        for thresh in candidate_thresholds:
            engine = VerdictEngine(similarity_threshold=thresh)
            
            pred_supported = 0
            pred_contradicted = 0
            pred_insufficient = 0
            
            true_supported_pred_supported = 0
            false_supported = 0
            
            true_contradicted_pred_contradicted = 0
            false_contradicted = 0
            
            false_approvals = 0  # Expected CONTRADICTED or INSUFFICIENT but predicted SUPPORTED
            
            for item, results in query_results:
                expected = item.get("expected_verdict")
                cv = engine.classify(
                    claim_id=item["id"],
                    claim_text=item["query"],
                    retrieved_passages=results,
                )
                pred = cv.verdict

                if pred == VERDICT_SUPPORTED:
                    pred_supported += 1
                    if expected == VERDICT_SUPPORTED:
                        true_supported_pred_supported += 1
                    else:
                        false_approvals += 1
                        false_supported += 1
                elif pred == VERDICT_CONTRADICTED:
                    pred_contradicted += 1
                    if expected == VERDICT_CONTRADICTED:
                        true_contradicted_pred_contradicted += 1
                    else:
                        false_contradicted += 1
                elif pred == VERDICT_INSUFFICIENT:
                    pred_insufficient += 1

            n_queries = len(query_results)
            supp_prec = true_supported_pred_supported / pred_supported if pred_supported > 0 else 0.0
            cont_prec = true_contradicted_pred_contradicted / pred_contradicted if pred_contradicted > 0 else 0.0
            false_app_rate = false_approvals / n_queries
            insuff_rate = pred_insufficient / n_queries
            
            # Ground truth distribution:
            # Expected Supported: sum(1 for it in benchmark_items if it.get('expected_verdict') == VERDICT_SUPPORTED)
            # Expected Contradicted: sum(1 for it in benchmark_items if it.get('expected_verdict') == VERDICT_CONTRADICTED)
            # Expected Insufficient: sum(1 for it in benchmark_items if it.get('expected_verdict') == VERDICT_INSUFFICIENT)
            
            record = {
                "threshold": thresh,
                "supported_precision": round(supp_prec, 4),
                "contradicted_precision": round(cont_prec, 4),
                "false_approval_rate": round(false_app_rate, 4),
                "insufficient_rate": round(insuff_rate, 4),
                "predicted_supported": pred_supported,
                "predicted_contradicted": pred_contradicted,
                "predicted_insufficient": pred_insufficient,
            }
            metrics.append(record)
            print(f"Thresh: {thresh:.2f} | SuppPrec: {supp_prec:.4f} | ContPrec: {cont_prec:.4f} | "
                  f"FalseApprovalRate: {false_app_rate:.4f} | InsuffRate: {insuff_rate:.4f} | "
                  f"(Supp: {pred_supported:2d}, Cont: {pred_contradicted:2d}, Insuff: {pred_insufficient:2d})")

        # Inspect distribution of top-1 similarities for relevant vs non-relevant
        top1_sims_relevant = []
        top1_sims_irrelevant = []
        for item, results in query_results:
            exp_chunks = set(item.get("expected_chunk_ids", []))
            if results:
                top_sim = results[0].get("similarity_score", 0.0)
                if exp_chunks:
                    top1_sims_relevant.append(top_sim)
                else:
                    top1_sims_irrelevant.append(top_sim)

        print("\nSIMILARITY SCORE DISTRIBUTION:")
        if top1_sims_relevant:
            print(f"Relevant queries Top-1 sim: min={min(top1_sims_relevant):.4f}, "
                  f"median={np.median(top1_sims_relevant):.4f}, mean={np.mean(top1_sims_relevant):.4f}, "
                  f"max={max(top1_sims_relevant):.4f}")
        if top1_sims_irrelevant:
            print(f"Irrelevant queries Top-1 sim: min={min(top1_sims_irrelevant):.4f}, "
                  f"median={np.median(top1_sims_irrelevant):.4f}, mean={np.mean(top1_sims_irrelevant):.4f}, "
                  f"max={max(top1_sims_irrelevant):.4f}")

        # Save to results
        res_path = os.path.join(os.path.dirname(__file__), "results", "threshold_calibration_results.json")
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump({
                "threshold_metrics": metrics,
                "relevant_top1_stats": {
                    "min": float(min(top1_sims_relevant)),
                    "median": float(np.median(top1_sims_relevant)),
                    "mean": float(np.mean(top1_sims_relevant)),
                    "max": float(max(top1_sims_relevant)),
                } if top1_sims_relevant else {},
                "irrelevant_top1_stats": {
                    "min": float(min(top1_sims_irrelevant)),
                    "median": float(np.median(top1_sims_irrelevant)),
                    "mean": float(np.mean(top1_sims_irrelevant)),
                    "max": float(max(top1_sims_irrelevant)),
                } if top1_sims_irrelevant else {}
            }, f, indent=2)
        print(f"\nSaved threshold calibration results to {res_path}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_experiment()
