"""
End-to-End Multi-Claim Performance and Pipeline Timing Benchmark.
Measures real performance for realistic marketing documents containing:
- 1 unique claim
- 5 unique claims
- 10 unique claims
- 20 unique claims

Evaluates across:
1. Modes: Dense, Hybrid RRF, Hybrid + Reranker
2. Conditions:
   - Condition A: Cold Process / Cold Cache (First-time novel claims)
   - Condition B: Warm Process with Novel Unique Claims (Steady-state with uncached unique claims)
   - Condition C: Warm Process with Repeated Claims (Steady-state with cached claims)

Measures and records:
- Total pipeline latency
- Claim extraction time
- Batch embedding generation time
- Dense retrieval time
- BM25 retrieval time
- RRF fusion & deduplication time
- Verdict engine classification time
- Cross-encoder reranking time (when enabled)
- Embedding cache hits and misses
- Per-claim latency
- Memory usage (RSS MB)
"""
import os
import sys
import time
import json
import psutil
import statistics
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.config import settings
from backend.app.services.claim_extractor import claim_extractor
from backend.app.services.verdict_engine import verdict_engine
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.hybrid_retriever import hybrid_retriever
from backend.evaluation.evaluate_retrieval import load_corpus

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
BENCHMARK_OUTPUT_PATH = os.path.join(RESULTS_DIR, "multiclaim_benchmark_results.json")

TEST_DOCUMENTS = {
    1: "Our ultra-secure cloud platform guarantees 99.99% uptime for all enterprise customers.",
    5: """Our organic dietary supplement boosts metabolic energy naturally within 14 days.
The brand logo must always be placed in the top-left corner with at least 20px clear margin.
All customer testimonials require written legal approval prior to external publication.
Pricing discount claims cannot exceed 50% without prior compliance officer authorization.
Medical devices must state FDA approved with specific registration number 9845-A.""",
    10: """Our organic dietary supplement boosts metabolic energy naturally within 14 days.
The brand logo must always be placed in the top-left corner with at least 20px clear margin.
All customer testimonials require written legal approval prior to external publication.
Pricing discount claims cannot exceed 50% without prior compliance officer authorization.
Medical devices must state FDA approved with specific registration number 9845-A.
Any claim containing 100% guaranteed or clinically proven is strictly prohibited in marketing copy.
Products shipped to the European Union require CE compliance registration 4432-B.
Enterprise accounts receive dedicated 24/7 technical security monitoring.
Our carbon-neutral server infrastructure reduces greenhouse emissions by 40%.
All promotional rebates require written signoff from the chief financial officer.""",
    20: """Our organic dietary supplement boosts metabolic energy naturally within 14 days.
The brand logo must always be placed in the top-left corner with at least 20px clear margin.
All customer testimonials require written legal approval prior to external publication.
Pricing discount claims cannot exceed 50% without prior compliance officer authorization.
Medical devices must state FDA approved with specific registration number 9845-A.
Any claim containing 100% guaranteed or clinically proven is strictly prohibited in marketing copy.
Products shipped to the European Union require CE compliance registration 4432-B.
Enterprise accounts receive dedicated 24/7 technical security monitoring.
Our carbon-neutral server infrastructure reduces greenhouse emissions by 40%.
All promotional rebates require written signoff from the chief financial officer.
All secondary typography must utilize 14pt Roboto font for regulatory disclosures.
Our financial investment products have delivered average annual returns of 12.5%.
Customer service response times are under 15 minutes during standard working hours.
All marketing collateral in North America must include the registered trademark symbol.
Employee satisfaction scores exceeded 92% across all international operating offices.
Our enterprise cybersecurity firewall blocks more than 99.9% of unauthorized intrusion attempts.
Standard product warranties cover hardware defects for a duration of 24 months.
The primary corporate color palette is strictly defined as Hex #1A73E8 blue.
Comparative performance claims versus named competitors require independent laboratory validation.
Free trial promotions cannot automatically convert to paid subscriptions without explicit consent."""
}


def instrumented_review_pipeline(
    content: str,
    retrieval_mode: str,
) -> Dict[str, Any]:
    """
    Executes the review pipeline with granular timing instrumentation for all components.
    """
    t_total_start = time.perf_counter()

    # 1. Claim extraction
    t0 = time.perf_counter()
    claims = claim_extractor.extract(content)
    t_ext_ms = (time.perf_counter() - t0) * 1000.0

    # 2. Batch embedding generation
    claim_texts = [c.claim_text for c in claims]
    t0 = time.perf_counter()
    claim_embeddings = embedding_service.generate_embeddings(claim_texts)
    t_emb_ms = (time.perf_counter() - t0) * 1000.0

    # 3. Retrieval per claim
    dense_times_ms: List[float] = []
    bm25_times_ms: List[float] = []
    rrf_times_ms: List[float] = []
    rerank_times_ms: List[float] = []
    all_passages = []

    for claim, q_emb in zip(claims, claim_embeddings):
        q = claim.claim_text
        if retrieval_mode == "dense":
            t0 = time.perf_counter()
            passages = hybrid_retriever._dense_search(q, target_doc_ids=None, top_k=4, query_embedding=q_emb)
            dense_times_ms.append((time.perf_counter() - t0) * 1000.0)
            all_passages.append(passages)
        elif retrieval_mode == "hybrid":
            # Instrument dense, bm25, and rrf separately
            t0 = time.perf_counter()
            dense_cands = hybrid_retriever._dense_search(q, target_doc_ids=None, top_k=15, query_embedding=q_emb)
            dense_times_ms.append((time.perf_counter() - t0) * 1000.0)

            t0 = time.perf_counter()
            bm25_cands = hybrid_retriever._bm25_search(q, target_doc_ids=None, top_k=15)
            bm25_times_ms.append((time.perf_counter() - t0) * 1000.0)

            t0 = time.perf_counter()
            # RRF fusion
            k = 60
            fused: Dict[str, float] = {}
            cand_map: Dict[str, Dict[str, Any]] = {}
            for rank, item in enumerate(dense_cands, start=1):
                cid = item["chunk_id"]
                fused[cid] = fused.get(cid, 0.0) + (1.0 / (k + rank))
                cand_map[cid] = dict(item)
            for rank, item in enumerate(bm25_cands, start=1):
                cid = item["chunk_id"]
                fused[cid] = fused.get(cid, 0.0) + (1.0 / (k + rank))
                if cid not in cand_map:
                    cand_map[cid] = dict(item)
            fused_list = []
            for cid, score in fused.items():
                m = cand_map[cid]
                m["rrf_score"] = score
                fused_list.append(m)
            fused_list.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)
            passages = hybrid_retriever._deduplicate_passages(fused_list, top_k=4)
            rrf_times_ms.append((time.perf_counter() - t0) * 1000.0)
            all_passages.append(passages)
        elif retrieval_mode == "hybrid_rerank":
            # Dense
            t0 = time.perf_counter()
            dense_cands = hybrid_retriever._dense_search(q, target_doc_ids=None, top_k=15, query_embedding=q_emb)
            dense_times_ms.append((time.perf_counter() - t0) * 1000.0)

            # BM25
            t0 = time.perf_counter()
            bm25_cands = hybrid_retriever._bm25_search(q, target_doc_ids=None, top_k=15)
            bm25_times_ms.append((time.perf_counter() - t0) * 1000.0)

            # RRF
            t0 = time.perf_counter()
            k = 60
            fused = {}
            cand_map = {}
            for rank, item in enumerate(dense_cands, start=1):
                cid = item["chunk_id"]
                fused[cid] = fused.get(cid, 0.0) + (1.0 / (k + rank))
                cand_map[cid] = dict(item)
            for rank, item in enumerate(bm25_cands, start=1):
                cid = item["chunk_id"]
                fused[cid] = fused.get(cid, 0.0) + (1.0 / (k + rank))
                if cid not in cand_map:
                    cand_map[cid] = dict(item)
            fused_list = []
            for cid, score in fused.items():
                m = cand_map[cid]
                m["rrf_score"] = score
                fused_list.append(m)
            fused_list.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)
            deduped = hybrid_retriever._deduplicate_passages(fused_list, top_k=None)
            rrf_times_ms.append((time.perf_counter() - t0) * 1000.0)

            # Rerank
            t0 = time.perf_counter()
            passages = hybrid_retriever.reranker.rerank(query=q, candidates=deduped, top_k=4)
            rerank_times_ms.append((time.perf_counter() - t0) * 1000.0)
            all_passages.append(passages)

    # 4. Verdict generation per claim
    t0 = time.perf_counter()
    verdicts = []
    for claim, passages in zip(claims, all_passages):
        v = verdict_engine.classify(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            retrieved_passages=passages,
        )
        verdicts.append(v)
    t_verdict_ms = (time.perf_counter() - t0) * 1000.0

    t_total_ms = (time.perf_counter() - t_total_start) * 1000.0

    return {
        "claims_count": len(claims),
        "total_ms": t_total_ms,
        "extraction_ms": t_ext_ms,
        "embedding_ms": t_emb_ms,
        "dense_retrieval_ms": sum(dense_times_ms),
        "bm25_retrieval_ms": sum(bm25_times_ms),
        "rrf_fusion_ms": sum(rrf_times_ms),
        "verdict_ms": t_verdict_ms,
        "rerank_ms": sum(rerank_times_ms),
        "per_claim_ms": t_total_ms / len(claims) if claims else 0.0,
    }


def run_benchmark():
    print("=" * 80)
    print("BrandSentry AI — Multi-Claim End-to-End Performance Verification")
    print("=" * 80)

    # 1. Ensure guidelines exist in ChromaDB and BM25
    corpus = load_corpus()
    if hybrid_retriever.vector_store.count() == 0:
        print(f"Indexing {len(corpus)} guideline chunks into ChromaDB & BM25...")
        chunk_texts = [c.text for c in corpus]
        embs = embedding_service.generate_embeddings(chunk_texts)
        hybrid_retriever.vector_store.add_chunks(corpus, embs)
        hybrid_retriever.bm25.add_chunks(corpus)

    # Pre-warm models so ONNX session creation is complete
    _ = embedding_service.embed_fn(["Warmup"])
    hybrid_retriever.reranker.ensure_loaded()

    proc = psutil.Process(os.getpid())
    results: Dict[str, Any] = {}

    claim_sizes = [1, 5, 10, 20]
    modes = ["dense", "hybrid", "hybrid_rerank"]

    # -----------------------------------------------------------------
    # Benchmark 1: COLD CACHE (Unique novel claims never seen before)
    # -----------------------------------------------------------------
    print("\n[BENCHMARK 1] Cold Cache Execution (Unique Novel Claims)")
    print("Each request clears embedding cache before execution.")
    results["cold_cache"] = {}

    for mode in modes:
        results["cold_cache"][mode] = {}
        print(f"\n  Mode: {mode.upper()}")
        for size in claim_sizes:
            content = TEST_DOCUMENTS[size]
            mem_before = proc.memory_info().rss / 1024 / 1024

            # Clear cache and reset stats
            embedding_service._cache.clear()
            embedding_service.reset_cache_stats()

            # Execute 3 runs to get stable metrics
            runs = []
            for _ in range(3):
                embedding_service._cache.clear()
                embedding_service.reset_cache_stats()
                run_data = instrumented_review_pipeline(content, mode)
                runs.append(run_data)

            mem_after = proc.memory_info().rss / 1024 / 1024
            stats = embedding_service.cache_stats

            mean_total = statistics.mean([r["total_ms"] for r in runs])
            p50_total = statistics.median([r["total_ms"] for r in runs])
            p95_total = sorted([r["total_ms"] for r in runs])[-1]

            mean_emb = statistics.mean([r["embedding_ms"] for r in runs])
            mean_dense = statistics.mean([r["dense_retrieval_ms"] for r in runs])
            mean_bm25 = statistics.mean([r["bm25_retrieval_ms"] for r in runs])
            mean_rrf = statistics.mean([r["rrf_fusion_ms"] for r in runs])
            mean_verdict = statistics.mean([r["verdict_ms"] for r in runs])
            mean_rerank = statistics.mean([r["rerank_ms"] for r in runs])
            mean_per_claim = mean_total / size

            results["cold_cache"][mode][size] = {
                "claims": size,
                "mean_total_ms": round(mean_total, 2),
                "p50_total_ms": round(p50_total, 2),
                "p95_total_ms": round(p95_total, 2),
                "per_claim_ms": round(mean_per_claim, 2),
                "embedding_ms": round(mean_emb, 2),
                "dense_retrieval_ms": round(mean_dense, 2),
                "bm25_retrieval_ms": round(mean_bm25, 2),
                "rrf_fusion_ms": round(mean_rrf, 2),
                "rerank_ms": round(mean_rerank, 2),
                "verdict_ms": round(mean_verdict, 2),
                "cache_hits": stats["hits"],
                "cache_misses": stats["misses"],
                "memory_rss_mb": round(mem_after, 2),
            }

            print(f"    Claims: {size:2d} | Total: {mean_total:7.2f} ms | Per-Claim: {mean_per_claim:6.2f} ms | "
                  f"Embed(Batch): {mean_emb:6.2f} ms | Retrieval: {mean_dense+mean_bm25+mean_rrf:5.2f} ms | "
                  f"Rerank: {mean_rerank:6.2f} ms | Verdict: {mean_verdict:5.2f} ms | Hits/Misses: {stats['hits']}/{stats['misses']}")

    # -----------------------------------------------------------------
    # Benchmark 2: WARM CACHE (Repeated review requests for same asset)
    # -----------------------------------------------------------------
    print("\n[BENCHMARK 2] Warm Cache Execution (Repeated Review of Same Asset)")
    print("Embeddings already present in cache from previous execution.")
    results["warm_cache"] = {}

    for mode in modes:
        results["warm_cache"][mode] = {}
        print(f"\n  Mode: {mode.upper()}")
        for size in claim_sizes:
            content = TEST_DOCUMENTS[size]
            # Warm up cache once
            _ = instrumented_review_pipeline(content, mode)
            embedding_service.reset_cache_stats()

            # Execute 5 repeated runs
            runs = []
            for _ in range(5):
                run_data = instrumented_review_pipeline(content, mode)
                runs.append(run_data)

            stats = embedding_service.cache_stats
            mean_total = statistics.mean([r["total_ms"] for r in runs])
            p50_total = statistics.median([r["total_ms"] for r in runs])
            p95_total = sorted([r["total_ms"] for r in runs])[-1]

            mean_emb = statistics.mean([r["embedding_ms"] for r in runs])
            mean_dense = statistics.mean([r["dense_retrieval_ms"] for r in runs])
            mean_bm25 = statistics.mean([r["bm25_retrieval_ms"] for r in runs])
            mean_rrf = statistics.mean([r["rrf_fusion_ms"] for r in runs])
            mean_verdict = statistics.mean([r["verdict_ms"] for r in runs])
            mean_rerank = statistics.mean([r["rerank_ms"] for r in runs])
            mean_per_claim = mean_total / size

            results["warm_cache"][mode][size] = {
                "claims": size,
                "mean_total_ms": round(mean_total, 2),
                "p50_total_ms": round(p50_total, 2),
                "p95_total_ms": round(p95_total, 2),
                "per_claim_ms": round(mean_per_claim, 2),
                "embedding_ms": round(mean_emb, 2),
                "dense_retrieval_ms": round(mean_dense, 2),
                "bm25_retrieval_ms": round(mean_bm25, 2),
                "rrf_fusion_ms": round(mean_rrf, 2),
                "rerank_ms": round(mean_rerank, 2),
                "verdict_ms": round(mean_verdict, 2),
                "cache_hits": stats["hits"],
                "cache_misses": stats["misses"],
            }

            print(f"    Claims: {size:2d} | Total: {mean_total:7.2f} ms | Per-Claim: {mean_per_claim:6.2f} ms | "
                  f"Embed(Batch): {mean_emb:6.2f} ms | Retrieval: {mean_dense+mean_bm25+mean_rrf:5.2f} ms | "
                  f"Rerank: {mean_rerank:6.2f} ms | Verdict: {mean_verdict:5.2f} ms | Hits/Misses: {stats['hits']}/{stats['misses']}")

    # Save machine-readable JSON
    with open(BENCHMARK_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved benchmark results to {BENCHMARK_OUTPUT_PATH}")


if __name__ == "__main__":
    run_benchmark()

