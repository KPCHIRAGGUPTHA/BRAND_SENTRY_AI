"""
Reproducible performance measurements for BrandSentry AI, covering the telemetry table in the
Round 3 report. Runs the real API in-process with empty temporary storage.

Usage: python scripts/measure_perf.py [--repeats 30] [--json results.json]

Results depend on the machine. They do not measure the deployed Render instance.
"""
import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="brandsentry_perf_")
os.environ["APP_ENV"] = "development"

import fitz  # noqa: E402
import psutil  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.retrieval.embeddings import embedding_service  # noqa: E402

SINGLE_CLAIM = "Customer data is completely secure."
TEN_CLAIMS = (
    "Our product is 100% guaranteed. Our product is 100% safe. This tea treats arthritis. "
    "Testimonials reflect genuine customer experiences. This is the lowest price ever. "
    "Our factory is carbon neutral. Our platform is impossible to hack. Evidence is retained for review. "
    "Our office is open on weekdays. We ship to over 30 countries."
)
REPORT = {
    "single_claim_ms": 42.8,
    "ten_claims_ms": 184.5,
    "pdf_20_pages_s": 1.82,
    "cache_hit_percent": 94.2,
    "rss_mb": 285,
}


def _twenty_page_pdf() -> bytes:
    paragraph = (
        "Marketing materials must be accurate and supported by documented evidence. "
        "Reviewers must retain records for every campaign and verify each factual statement. "
    ) * 12
    document = fitz.open()
    for number in range(20):
        document.new_page().insert_textbox(
            fitz.Rect(40, 40, 560, 800), f"Section {number + 1}. {paragraph}", fontsize=10
        )
    return document.tobytes()


def _median_ms(client, content, document_ids, repeats):
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.post("/api/review", json={"content": content, "document_ids": document_ids})
        samples.append((time.perf_counter() - started) * 1000)
        response.raise_for_status()
    return round(statistics.median(samples), 1), round(max(samples), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--json")
    args = parser.parse_args()

    client = TestClient(app)
    process = psutil.Process()

    started = time.perf_counter()
    embedding_service.generate_embeddings(["model load"])
    model_load_s = round(time.perf_counter() - started, 2)

    sample = client.post("/api/guidelines/load-sample")
    sample.raise_for_status()
    document_ids = [sample.json()["document_id"]]

    started = time.perf_counter()
    upload = client.post(
        "/api/guidelines/upload",
        files={"file": ("perf_20_pages.pdf", _twenty_page_pdf(), "application/pdf")},
    )
    pdf_seconds = round(time.perf_counter() - started, 2)
    upload.raise_for_status()

    embedding_service.reset_cache_stats()
    single_median, single_worst = _median_ms(client, SINGLE_CLAIM, document_ids, args.repeats)
    single_stats = dict(embedding_service.cache_stats)

    embedding_service.reset_cache_stats()
    ten_median, ten_worst = _median_ms(client, TEN_CLAIMS, document_ids, args.repeats)

    embedding_service.reset_cache_stats()
    client.post("/api/review", json={"content": "A brand new sentence about shipping policy.", "document_ids": document_ids})
    client.post("/api/review", json={"content": "Another unseen statement about our returns.", "document_ids": document_ids})
    unique_stats = dict(embedding_service.cache_stats)

    def hit_percent(stats):
        lookups = stats["hits"] + stats["misses"]
        return round(100 * stats["hits"] / lookups, 1) if lookups else None

    results = {
        "environment": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}, "
                       f"{psutil.cpu_count()} CPUs",
        "model_load_s": model_load_s,
        "single_claim_ms": single_median,
        "single_claim_worst_ms": single_worst,
        "ten_claims_ms": ten_median,
        "ten_claims_worst_ms": ten_worst,
        "pdf_20_pages_s": pdf_seconds,
        "pdf_20_pages_chunks": upload.json()["chunk_count"],
        "cache_hit_percent_same_claim_repeated": hit_percent(single_stats),
        "cache_hit_percent_all_new_claims": hit_percent(unique_stats),
        "rss_mb": round(process.memory_info().rss / (1024 * 1024)),
        "report_claims": REPORT,
    }
    print(json.dumps(results, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
