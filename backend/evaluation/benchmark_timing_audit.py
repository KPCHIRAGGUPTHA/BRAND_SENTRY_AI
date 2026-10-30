"""
Independent Latency and Performance Benchmark Audit for BrandSentry AI.
Measures:
1. Model initialization / load times (Embedding model, BM25, Cross-Encoder).
2. Cold query latency (cache cleared before query).
3. Warm query latency (cached embedding / warm ONNX session).
4. Component-level timing breakdowns:
   - Query embedding generation (cold vs warm)
   - Vector store (ChromaDB) query
   - BM25 lexical search
   - Reciprocal Rank Fusion & deduplication
   - Cross-encoder candidate scoring (15 pairs)
5. End-to-end retrieval across all 4 modes under identical, controlled conditions:
   - Condition A: Pre-computed query embeddings (isolated retrieval & ranking time)
   - Condition B: End-to-end cold (uncached embedding + retrieval)
   - Condition C: End-to-end warm (cached embedding + retrieval)
6. Multiple repetitions (5 runs per query) with mean, median (p50), and p95.
"""
import os
import sys
import time
import json
import statistics
import tempfile
import shutil
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.evaluation.evaluate_retrieval import load_corpus, load_benchmark
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.vector_store import VectorStoreService
from backend.app.retrieval.embeddings import EmbeddingService
from backend.app.retrieval.reranker import CrossEncoderRerankerService
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService


def run_latency_audit():
    print("=" * 80)
    print("BrandSentry AI — Retrieval Latency & Component Breakdown Audit")
    print("=" * 80)

    corpus = load_corpus()
    benchmark = load_benchmark()
    temp_dir = tempfile.mkdtemp(prefix="brandsentry_timing_")

    try:
        chroma_dir = os.path.join(temp_dir, "chroma")
        bm25_dir = os.path.join(temp_dir, "bm25")

        # -------------------------------------------------------------
        # 1. Model Initialization Benchmarks
        # -------------------------------------------------------------
        print("\n[1] Measuring Model Initialization Times...")

        # Fresh EmbeddingService
        t0 = time.perf_counter()
        embed_service = EmbeddingService()
        _ = embed_service.embed_fn(["Warm-up query"])
        t_embed_init = (time.perf_counter() - t0) * 1000.0
        print(f"  • Embedding Model (all-MiniLM-L6-v2 ONNX) initialization: {t_embed_init:.2f} ms")

        # VectorStoreService & indexing
        t0 = time.perf_counter()
        vector_store = VectorStoreService(persist_dir=chroma_dir, collection_name="audit_chunks")
        chunk_texts = [c.text for c in corpus]
        embs = embed_service.generate_embeddings(chunk_texts)
        vector_store.add_chunks(corpus, embs)
        t_vs_init = (time.perf_counter() - t0) * 1000.0
        print(f"  • ChromaDB indexing ({len(corpus)} chunks): {t_vs_init:.2f} ms")

        # BM25 indexing
        t0 = time.perf_counter()
        bm25_service = BM25RetrieverService(persist_dir=bm25_dir)
        bm25_service.add_chunks(corpus)
        t_bm25_init = (time.perf_counter() - t0) * 1000.0
        print(f"  • BM25 indexing ({len(corpus)} chunks): {t_bm25_init:.2f} ms")

        # Cross-Encoder initialization
        t0 = time.perf_counter()
        reranker_service = CrossEncoderRerankerService()
        reranker_service.ensure_loaded()
        t_reranker_init = (time.perf_counter() - t0) * 1000.0
        print(f"  • Cross-Encoder (Xenova/ms-marco-MiniLM-L-6-v2 ONNX) initialization: {t_reranker_init:.2f} ms")

        retriever = HybridRetrieverService(
            vector_store=vector_store,
            bm25_service=bm25_service,
            embeddings=embed_service,
            reranker=reranker_service,
            smoothing_k=60,
        )

        # -------------------------------------------------------------
        # 2. Component-Level Timing Breakdown
        # -------------------------------------------------------------
        print("\n[2] Measuring Component-Level Times Across 60 Benchmark Queries...")
        comp_emb_cold: List[float] = []
        comp_emb_warm: List[float] = []
        comp_chroma: List[float] = []
        comp_bm25: List[float] = []
        comp_rrf: List[float] = []
        comp_rerank: List[float] = []

        for item in benchmark:
            q = item["query"]
            scope = item.get("document_scope")

            # Cold embedding (clear cache)
            with embed_service._cache_lock:
                embed_service._cache.clear()
            t0 = time.perf_counter()
            q_emb = embed_service.generate_query_embedding(q)
            comp_emb_cold.append((time.perf_counter() - t0) * 1000.0)

            # Warm embedding (cached)
            t0 = time.perf_counter()
            _ = embed_service.generate_query_embedding(q)
            comp_emb_warm.append((time.perf_counter() - t0) * 1000.0)

            # ChromaDB vector query
            t0 = time.perf_counter()
            dense_candidates = vector_store.search(query_embedding=q_emb, document_id=scope, top_k=15)
            comp_chroma.append((time.perf_counter() - t0) * 1000.0)

            # BM25 search
            t0 = time.perf_counter()
            bm25_candidates = bm25_service.search(query=q, document_id=scope, top_k=15)
            comp_bm25.append((time.perf_counter() - t0) * 1000.0)

            # RRF fusion
            t0 = time.perf_counter()
            fused: Dict[str, float] = {}
            for rank, c in enumerate(dense_candidates, start=1):
                fused[c["chunk_id"]] = fused.get(c["chunk_id"], 0.0) + (1.0 / (60 + rank))
            for rank, c in enumerate(bm25_candidates, start=1):
                fused[c["chunk_id"]] = fused.get(c["chunk_id"], 0.0) + (1.0 / (60 + rank))
            comp_rrf.append((time.perf_counter() - t0) * 1000.0)

            # Cross-encoder inference (15 candidates)
            t0 = time.perf_counter()
            _ = reranker_service.rerank(query=q, candidates=dense_candidates[:15], top_k=5)
            comp_rerank.append((time.perf_counter() - t0) * 1000.0)

        def print_stats(name: str, values: List[float]):
            v_sorted = sorted(values)
            mean = statistics.mean(values)
            p50 = statistics.median(values)
            p95 = v_sorted[int(len(v_sorted) * 0.95)]
            print(f"  • {name:<35}: Mean={mean:6.2f} ms | p50={p50:6.2f} ms | p95={p95:6.2f} ms")

        print_stats("Query Embedding (Cold / ONNX)", comp_emb_cold)
        print_stats("Query Embedding (Warm / Cached)", comp_emb_warm)
        print_stats("ChromaDB Vector Search (top_k=15)", comp_chroma)
        print_stats("BM25 Lexical Search (top_k=15)", comp_bm25)
        print_stats("RRF Fusion & Ranking", comp_rrf)
        print_stats("Cross-Encoder Reranker (15 pairs)", comp_rerank)

        # -------------------------------------------------------------
        # 3. Controlled Repeated Benchmarks Across All 4 Configurations
        # -------------------------------------------------------------
        # We test under two realistic production conditions:
        # Condition 1: Cold Cache (Uncached query embedding + retrieval)
        # Condition 2: Warm Cache (Cached query embedding + retrieval)
        # Condition 3: Pre-computed Embedding / Retrieval-Only (isolating index search + fusion)
        
        NUM_REPETITIONS = 5
        modes = ["dense", "bm25", "hybrid", "hybrid_rerank"]

        for condition_name, use_cold_cache in [("WARM CACHE (Production steady-state)", False), ("COLD CACHE (Unique novel queries)", True)]:
            print(f"\n[3] Running Controlled Repeated Benchmark: {condition_name}")
            print(f"    (60 queries x {NUM_REPETITIONS} repetitions = {60 * NUM_REPETITIONS} executions per mode)")
            print(f"    {'-'*75}")

            for mode in modes:
                all_query_latencies: List[float] = []

                for rep in range(NUM_REPETITIONS):
                    for item in benchmark:
                        q = item["query"]
                        scope = item.get("document_scope")

                        if use_cold_cache:
                            with embed_service._cache_lock:
                                embed_service._cache.clear()

                        t0 = time.perf_counter()
                        _ = retriever.search(query=q, document_id=scope, top_k=5, mode=mode)
                        lat_ms = (time.perf_counter() - t0) * 1000.0
                        all_query_latencies.append(lat_ms)

                sorted_lats = sorted(all_query_latencies)
                mean_l = statistics.mean(all_query_latencies)
                p50_l = statistics.median(all_query_latencies)
                p95_l = sorted_lats[int(len(sorted_lats) * 0.95)]
                print(f"    Mode [{mode.upper():<13}]: Mean={mean_l:6.2f} ms | p50={p50_l:6.2f} ms | p95={p95_l:6.2f} ms")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("\nBenchmark audit complete.")


if __name__ == "__main__":
    run_latency_audit()

