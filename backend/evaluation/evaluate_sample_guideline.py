"""
Sample Guideline Evaluation for BrandSentry AI.
Uploads a guideline to a running backend and reviews every labelled case through the real
HTTP API. Case labels are written from the guideline text, not from engine output.

Usage: python backend/evaluation/evaluate_sample_guideline.py [--base-url URL] [--dataset PATH] [--guideline PATH]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "backend/evaluation/datasets/sample_guideline_cases.jsonl"
DEFAULT_GUIDELINE = ROOT / "BrandSentry_Sample_Marketing_Compliance_Guidelines.txt"


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def evaluate_case(case: dict, claim: dict, guideline_text: str) -> list:
    """Returns the problems found for one reviewed claim; empty means the case passed."""
    problems = []
    if claim["verdict"] != case["expected"]:
        problems.append(f"expected {case['expected']}, got {claim['verdict']}")
    if claim["verdict"] != claim.get("compliance_verdict"):
        problems.append("verdict != compliance_verdict")
    quotes = [_normalize(e["quote"]) for e in claim["evidence"]]
    for quote in quotes:
        if quote not in guideline_text:
            problems.append(f"citation is not in the guideline: {quote[:60]}")
    if case["expected"] != "INSUFFICIENT_EVIDENCE" and case.get("cite"):
        if not any(_normalize(c) in q for c in case["cite"] for q in quotes):
            problems.append(f"missing citation for {case['cite']}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--guideline", default=str(DEFAULT_GUIDELINE))
    args = parser.parse_args()

    guideline_path = Path(args.guideline)
    guideline_text = _normalize(guideline_path.read_text(encoding="utf-8"))
    lines = Path(args.dataset).read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=240) as client:
        upload = client.post(
            "/api/guidelines/upload",
            files={"file": (guideline_path.name, guideline_path.read_bytes(), "text/plain")},
        )
        upload.raise_for_status()
        document_id = upload.json()["document_id"]
        print(f"uploaded {guideline_path.name}: {upload.json()['chunk_count']} chunks")

        failures = 0
        confusion = Counter()
        for case in cases:
            response = client.post(
                "/api/review",
                json={"content": case["claim"], "document_ids": [document_id]},
            )
            response.raise_for_status()
            claims = response.json()["claims"]
            if len(claims) == 1:
                problems = evaluate_case(case, claims[0], guideline_text)
            else:
                problems = [f"extracted {len(claims)} claims"]
            confusion[(case["expected"], claims[0]["verdict"] if claims else "NONE")] += 1
            if problems:
                failures += 1
                print(f"FAIL {case['id']}: {case['claim']}\n     {'; '.join(problems)}")

    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    for (expected, got), count in sorted(confusion.items()):
        print(f"  expected {expected:22} got {got:22} {count}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
