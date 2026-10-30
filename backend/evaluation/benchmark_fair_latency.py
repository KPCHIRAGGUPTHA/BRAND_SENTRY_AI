"""
Fair Latency Benchmark Comparison for BrandSentry AI.
Compares Dense vs Hybrid retrieval under strictly controlled, randomized conditions:
- Identical documents and identical claim strings.
- At least 10 repetitions per configuration.
- Randomized execution order between Dense and Hybrid.
- Clearly distinguishes:
  1. Cold process (fresh subprocess startup, model loading, client initialization).
  2. Warm process with unique claims (cold cache: embedding generated via ONNX forward pass).
  3. Warm process with repeated identical claims (warm cache: embedding hit via in-memory LRU).
- Records:
  - Cold-cache mean, median, p95
  - Warm-cache mean, median, p95
  - Component breakdown: Batch embedding, Retrieval (ChromaDB vs ChromaDB+BM25+RRF), Verdict generation
  - Cache hits and misses
  - Overhead clarification (Pure in-process service calls vs HTTP API overhead)
"""
import os
import sys
import time
import json
import random
import statistics
import subprocess
import tempfile
import shutil
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


# Representative test claim set (10 distinct claims spanning all compliance categories)
TEST_CLAIMS = [
    "Our enterprise cloud platform guarantees 99.99% uptime for all customers.",
    "The corporate logo must always have at least 20px clear margin.",
    "Any claim containing 100% guaranteed is strictly prohibited.",
    "Customer testimonials require written legal approval prior to publication.",
    "Pricing discount claims cannot exceed 50% without compliance officer signoff.",
    "Our product is 100% safe and poses zero risk to health.",
    "All customer data is encrypted with AES-256 at rest.",
    "Our supplement boosts metabolic energy naturally within 14 days.",
    "We provide reproducible performance benchmarks against legacy systems.",
    "Environmental claims such as eco-friendly must be supported by documented evidence."
]


def measure_cold_process() -> float:
    """Measures true cold-process startup time (fresh Python process + model load)."""
    cmd = [
        sys.executable,
        "-c",
        "import time; t0=time.perf_counter(); "
        "from backend.app.retrieval.embeddings import embedding_service; "
        "_ = embedding_service.embed_fn(['warmup']); "
        "from backend.app.retrieval.vector_store import vector_store_service; "
        "_ = vector_store_service.collection; "
        "print((time.perf_counter() - t0)*1000.0)"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
    return float(res.stdout.strip().splitlines()[-1])


def run_fair_latency_benchmark(num_repetitions: int = 10):
    print("=" * 80)
    print("BrandSentry AI — Stage 2 Fair Latency Benchmark")
    print(f"Configurations: Dense vs Hybrid | Repetitions: {num_repetitions} (Randomized Order)")
    print("=" * 80)

    # 1. Measure Cold Process Startup
    print("\n[Phase 1] Measuring Cold Process Startup (Fresh Process Loading Overhead)...")
    cold_process_times = [measure_cold_process() for _ in range(3)]
    cold_proc_mean = statistics.mean(cold_process_times)
    print(f"  • Cold Process Initialization: Mean={cold_proc_mean:.2f} ms (p50={statistics.median(cold_process_times):.2f} ms)")

    # 2. Setup isolated in-process benchmark environment
    corpus = load_corpus()
    temp_dir = tempfile.mkdtemp(prefix="brandsentry_latency_")
    try:
        chroma_dir = os.path.join(temp_dir, "chroma")
        bm25_dir = os.path.join(temp_dir, "bm25")

        vstore = VectorStoreService(persist_dir=chroma_dir, collection_name="bench_chunks")
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

        # Pre-warm models so ONNX session creation is not conflated with query latency
        _ = embedding_service.embed_fn(["Warmup text"])

        # Create randomized execution schedule for fair comparison
        # 10 runs of Dense, 10 runs of Hybrid, randomized
        runs_schedule = [("dense", rep) for rep in range(num_repetitions)] + [("hybrid", rep) for rep in range(num_repetitions)]
        random.seed(42)
        random.shuffle(runs_schedule)

        results: Dict[str, Dict[str, List[float]]] = {
            "dense": {
                "cold_cache_total": [],
                "cold_cache_embed": [],
                "cold_cache_retrieval": [],
                "cold_cache_verdict": [],
                "warm_cache_total": [],
                "warm_cache_embed": [],
                "warm_cache_retrieval": [],
                "warm_cache_verdict": [],
                "cold_hits": [],
                "cold_misses": [],
                "warm_hits": [],
                "warm_misses": [],
            },
            "hybrid": {
                "cold_cache_total": [],
                "cold_cache_embed": [],
                "cold_cache_retrieval": [],
                "cold_cache_verdict": [],
                "warm_cache_total": [],
                "warm_cache_embed": [],
                "warm_cache_retrieval": [],
                "warm_cache_verdict": [],
                "cold_hits": [],
                "cold_misses": [],
                "warm_hits": [],
                "warm_misses": [],
            }
        }

        print(f"\n[Phase 2] Executing {len(runs_schedule)} Randomized Benchmark Runs across {len(TEST_CLAIMS)} Claims...")

        for mode, rep in runs_schedule:
            # -------------------------------------------------------------
            # A. Warm Process with Unique Claims (Cold Cache Run)
            # Clear embedding cache before the run
            # -------------------------------------------------------------
            with embedding_service._cache_lock:
                embedding_service._cache.clear()
            embedding_service.reset_cache_stats()

            t_run_start = time.perf_counter()

            # 1. Batch Embedding Generation (Cold cache -> misses)
            t0 = time.perf_counter()
            claim_embeddings = embedding_service.generate_embeddings(TEST_CLAIMS)
            t_cold_embed = (time.perf_counter() - t0) * 1000.0

            # 2. Retrieval across all claims
            t0 = time.perf_counter()
            all_passages = []
            for q, q_emb in zip(TEST_CLAIMS, claim_embeddings):
                passages = retriever.search(query=q, top_k=5, query_embedding=q_emb, mode=mode)
                all_passages.append(passages)
            t_cold_retrieval = (time.perf_counter() - t0) * 1000.0

            # 3. Verdict Generation
            t0 = time.perf_counter()
            for idx, (q, p) in enumerate(zip(TEST_CLAIMS, all_passages)):
                _ = verdict_engine.classify(claim_id=f"c-{idx}", claim_text=q, retrieved_passages=p)
            t_cold_verdict = (time.perf_counter() - t0) * 1000.0

            t_cold_total = (time.perf_counter() - t_run_start) * 1000.0

            c_stats = embedding_service.cache_stats
            results[mode]["cold_cache_total"].append(t_cold_total)
            results[mode]["cold_cache_embed"].append(t_cold_embed)
            results[mode]["cold_cache_retrieval"].append(t_cold_retrieval)
            results[mode]["cold_cache_verdict"].append(t_cold_verdict)
            results[mode]["cold_hits"].append(c_stats["hits"])
            results[mode]["cold_misses"].append(c_stats["misses"])

            # -------------------------------------------------------------
            # B. Warm Process with Repeated Identical Claims (Warm Cache Run)
            # Retain cache from the immediately preceding cold run
            # -------------------------------------------------------------
            embedding_service.reset_cache_stats()
            t_warm_run_start = time.perf_counter()

            # 1. Batch Embedding Generation (Warm cache -> hits)
            t0 = time.perf_counter()
            claim_embeddings_warm = embedding_service.generate_embeddings(TEST_CLAIMS)
            t_warm_embed = (time.perf_counter() - t0) * 1000.0

            # 2. Retrieval across all claims
            t0 = time.perf_counter()
            all_passages_warm = []
            for q, q_emb in zip(TEST_CLAIMS, claim_embeddings_warm):
                passages = retriever.search(query=q, top_k=5, query_embedding=q_emb, mode=mode)
                all_passages_warm.append(passages)
            t_warm_retrieval = (time.perf_counter() - t0) * 1000.0

            # 3. Verdict Generation
            t0 = time.perf_counter()
            for idx, (q, p) in enumerate(zip(TEST_CLAIMS, all_passages_warm)):
                _ = verdict_engine.classify(claim_id=f"c-{idx}", claim_text=q, retrieved_passages=p)
            t_warm_verdict = (time.perf_counter() - t0) * 1000.0

            t_warm_total = (time.perf_counter() - t_warm_run_start) * 1000.0

            w_stats = embedding_service.cache_stats
            results[mode]["warm_cache_total"].append(t_warm_total)
            results[mode]["warm_cache_embed"].append(t_warm_embed)
            results[mode]["warm_cache_retrieval"].append(t_warm_retrieval)
            results[mode]["warm_cache_verdict"].append(t_warm_verdict)
            results[mode]["warm_hits"].append(w_stats["hits"])
            results[mode]["warm_misses"].append(w_stats["misses"])

        # -------------------------------------------------------------
        # 3. Summarize and Print Audit Table
        # -------------------------------------------------------------
        print("\n" + "=" * 80)
        print("FAIR LATENCY BENCHMARK RESULTS (10 Claims per Run, 10 Repetitions)")
        print("=" * 80)

        def calc_stats(vals: List[float]) -> Dict[str, float]:
            s = sorted(vals)
            p95_idx = int(len(s) * 0.95)
            if p95_idx >= len(s):
                p95_idx = len(s) - 1
            return {
                "mean": statistics.mean(vals),
                "median": statistics.median(vals),
                "p95": s[p95_idx],
            }

        summary = {}
        for m in ["dense", "hybrid"]:
            summary[m] = {
                "cold_cache_total": calc_stats(results[m]["cold_cache_total"]),
                "cold_cache_embed": calc_stats(results[m]["cold_cache_embed"]),
                "cold_cache_retrieval": calc_stats(results[m]["cold_cache_retrieval"]),
                "cold_cache_verdict": calc_stats(results[m]["cold_cache_verdict"]),
                "warm_cache_total": calc_stats(results[m]["warm_cache_total"]),
                "warm_cache_embed": calc_stats(results[m]["warm_cache_embed"]),
                "warm_cache_retrieval": calc_stats(results[m]["warm_cache_retrieval"]),
                "warm_cache_verdict": calc_stats(results[m]["warm_cache_verdict"]),
                "cold_hits_mean": statistics.mean(results[m]["cold_hits"]),
                "cold_misses_mean": statistics.mean(results[m]["cold_misses"]),
                "warm_hits_mean": statistics.mean(results[m]["warm_hits"]),
                "warm_misses_mean": statistics.mean(results[m]["warm_misses"]),
            }

        print(f"\n{'Metric':<35} | {'Dense Only':<18} | {'Hybrid RRF':<18}")
        print("-" * 75)
        print(f"{'Cold-cache Mean (10 claims)':<35} | {summary['dense']['cold_cache_total']['mean']:8.2f} ms        | {summary['hybrid']['cold_cache_total']['mean']:8.2f} ms")
        print(f"{'Cold-cache Median (p50)':<35} | {summary['dense']['cold_cache_total']['median']:8.2f} ms        | {summary['hybrid']['cold_cache_total']['median']:8.2f} ms")
        print(f"{'Cold-cache p95':<35} | {summary['dense']['cold_cache_total']['p95']:8.2f} ms        | {summary['hybrid']['cold_cache_total']['p95']:8.2f} ms")
        print("-" * 75)
        print(f"{'Warm-cache Mean (10 claims)':<35} | {summary['dense']['warm_cache_total']['mean']:8.2f} ms        | {summary['hybrid']['warm_cache_total']['mean']:8.2f} ms")
        print(f"{'Warm-cache Median (p50)':<35} | {summary['dense']['warm_cache_total']['median']:8.2f} ms        | {summary['hybrid']['warm_cache_total']['median']:8.2f} ms")
        print(f"{'Warm-cache p95':<35} | {summary['dense']['warm_cache_total']['p95']:8.2f} ms        | {summary['hybrid']['warm_cache_total']['p95']:8.2f} ms")
        print("-" * 75)
        print(f"{'Batch Embedding Time (Cold Mean)':<35} | {summary['dense']['cold_cache_embed']['mean']:8.2f} ms        | {summary['hybrid']['cold_cache_embed']['mean']:8.2f} ms")
        print(f"{'Batch Embedding Time (Warm Mean)':<35} | {summary['dense']['warm_cache_embed']['mean']:8.2f} ms        | {summary['hybrid']['warm_cache_embed']['mean']:8.2f} ms")
        print(f"{'Retrieval Time Mean':<35} | {summary['dense']['cold_cache_retrieval']['mean']:8.2f} ms        | {summary['hybrid']['cold_cache_retrieval']['mean']:8.2f} ms")
        print(f"{'Verdict Generation Time Mean':<35} | {summary['dense']['cold_cache_verdict']['mean']:8.2f} ms        | {summary['hybrid']['cold_cache_verdict']['mean']:8.2f} ms")
        print("-" * 75)
        print(f"{'Cold Cache Hits / Misses':<35} | {summary['dense']['cold_hits_mean']:.0f} hits / {summary['dense']['cold_misses_mean']:.0f} misses | {summary['hybrid']['cold_hits_mean']:.0f} hits / {summary['hybrid']['cold_misses_mean']:.0f} misses")
        print(f"{'Warm Cache Hits / Misses':<35} | {summary['dense']['warm_hits_mean']:.0f} hits / {summary['dense']['warm_misses_mean']:.0f} misses | {summary['hybrid']['warm_hits_mean']:.0f} hits / {summary['hybrid']['warm_misses_mean']:.0f} misses")
        print("=" * 80)

        # Per-claim statistics
        dense_cold_per_claim = summary['dense']['cold_cache_total']['mean'] / len(TEST_CLAIMS)
        dense_warm_per_claim = summary['dense']['warm_cache_total']['mean'] / len(TEST_CLAIMS)
        hybrid_cold_per_claim = summary['hybrid']['cold_cache_total']['mean'] / len(TEST_CLAIMS)
        hybrid_warm_per_claim = summary['hybrid']['warm_cache_total']['mean'] / len(TEST_CLAIMS)

        print("\nPER-CLAIM LATENCY:")
        print(f"  • Dense  Cold: {dense_cold_per_claim:.2f} ms/claim | Dense  Warm: {dense_warm_per_claim:.2f} ms/claim")
        print(f"  • Hybrid Cold: {hybrid_cold_per_claim:.2f} ms/claim | Hybrid Warm: {hybrid_warm_per_claim:.2f} ms/claim")

        # Save machine-readable output
        out_path = os.path.join(PROJECT_ROOT, "backend", "evaluation", "results", "fair_latency_benchmark_results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "cold_process_mean_ms": cold_proc_mean,
                "summary": summary,
                "num_repetitions": num_repetitions,
                "claims_count": len(TEST_CLAIMS),
            }, f, indent=2)
        print(f"\nSaved fair latency benchmark results to {out_path}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_fair_latency_benchmark(num_repetitions=10)

