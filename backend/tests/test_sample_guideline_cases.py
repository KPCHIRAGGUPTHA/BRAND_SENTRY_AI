"""
Labelled cases for the bundled sample guideline and an unrelated second guideline, run through
real extraction, chunking, embeddings, hybrid retrieval and the verdict engine. Nothing is mocked.
Labels come from the guideline text, not from engine output.
"""
import json
from pathlib import Path

import pytest

from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService
from backend.app.retrieval.vector_store import VectorStoreService
from backend.app.services.chunking import DocumentChunker
from backend.app.services.claim_extractor import claim_extractor
from backend.app.services.extraction import DocumentExtractor
from backend.app.services.verdict_engine import (
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
    VERDICT_SUPPORTED,
    verdict_engine,
)
from backend.evaluation.evaluate_sample_guideline import _normalize

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "backend/evaluation/datasets"
SAMPLE_GUIDELINE = ROOT / "BrandSentry_Sample_Marketing_Compliance_Guidelines.txt"
OTHER_GUIDELINE = DATASETS / "generalization_guideline.txt"


def _load_cases(name):
    lines = (DATASETS / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


class Pipeline:
    """The real review pipeline over one uploaded guideline, using temporary storage."""

    def __init__(self, guideline_path, storage):
        self.text = _normalize(guideline_path.read_text(encoding="utf-8"))
        self.document_id = guideline_path.stem
        extracted = DocumentExtractor.extract_text(guideline_path.name, guideline_path.read_bytes())
        chunks = DocumentChunker().chunk_document(self.document_id, extracted)
        vectors = VectorStoreService(persist_dir=str(storage / "chroma"))
        vectors.add_chunks(chunks, embedding_service.generate_embeddings([c.text for c in chunks]))
        bm25 = BM25RetrieverService(persist_dir=str(storage / "bm25"))
        bm25.add_chunks(chunks)
        self.retriever = HybridRetrieverService(vector_store=vectors, bm25_service=bm25)

    def review(self, claim_id, claim_text):
        passages = self.retriever.search(query=claim_text, document_ids=[self.document_id], top_k=5)
        return verdict_engine.classify(claim_id, claim_text, passages)


@pytest.fixture(scope="module")
def sample_pipeline(tmp_path_factory):
    return Pipeline(SAMPLE_GUIDELINE, tmp_path_factory.mktemp("sample"))


@pytest.fixture(scope="module")
def other_pipeline(tmp_path_factory):
    return Pipeline(OTHER_GUIDELINE, tmp_path_factory.mktemp("other"))


def _assert_case(pipeline, case):
    result = pipeline.review(case["id"], case["claim"])
    assert result.verdict == case["expected"], f"{case['claim']}: {result.explanation}"
    assert result.verdict == result.compliance_verdict

    quotes = [_normalize(e.quote) for e in result.evidence]
    for quote in quotes:
        assert quote in pipeline.text, f"citation is not in the guideline: {quote}"
    if case["expected"] != VERDICT_INSUFFICIENT and case.get("cite"):
        assert any(_normalize(c) in q for c in case["cite"] for q in quotes), f"{case['claim']}: {quotes}"
    if result.suggested_correction:
        assert result.suggested_correction.startswith("[DRAFT")


@pytest.mark.parametrize("case", _load_cases("sample_guideline_cases.jsonl"), ids=lambda c: c["id"])
def test_sample_guideline_case(sample_pipeline, case):
    _assert_case(sample_pipeline, case)


@pytest.mark.parametrize("case", _load_cases("sample_guideline_sealed_cases.jsonl"), ids=lambda c: c["id"])
def test_sample_guideline_sealed_case(sample_pipeline, case):
    _assert_case(sample_pipeline, case)


@pytest.mark.parametrize("case", _load_cases("generalization_cases.jsonl"), ids=lambda c: c["id"])
def test_other_guideline_case(other_pipeline, case):
    _assert_case(other_pipeline, case)


def test_multi_claim_copy_gets_one_verdict_per_claim(sample_pipeline):
    copy = (
        "Our product is 100% safe. Customer data is completely secure. "
        "Testimonials reflect genuine customer experiences. Our office is open on weekdays."
    )
    verdicts = [sample_pipeline.review(c.claim_id, c.claim_text).verdict for c in claim_extractor.extract(copy)]
    assert verdicts == [
        VERDICT_CONTRADICTED,
        VERDICT_CONTRADICTED,
        VERDICT_SUPPORTED,
        VERDICT_INSUFFICIENT,
    ]


@pytest.mark.parametrize(
    "claim",
    [
        "Our product is 100% safe without any side effects.",
        "We don't share data and our platform is impossible to hack.",
        "Not only is customer data completely secure, it is fast.",
    ],
)
def test_nearby_negation_does_not_excuse_a_violation(sample_pipeline, claim):
    assert sample_pipeline.review("neg", claim).verdict == VERDICT_CONTRADICTED


@pytest.mark.parametrize(
    "claim",
    [
        "Our manager orally approved calling this the lowest price ever.",
        "Pricing records from five years ago show this is the lowest price ever.",
    ],
)
def test_oral_approval_and_stale_records_do_not_meet_an_exception(sample_pipeline, claim):
    assert sample_pipeline.review("exc", claim).verdict == VERDICT_CONTRADICTED


def test_claimed_approval_is_never_supported(sample_pipeline):
    result = sample_pipeline.review("exc", "Historical pricing records confirm this is the lowest price ever.")
    assert result.verdict == VERDICT_INSUFFICIENT
    assert result.evidence, "the exception rule should still be cited for the reviewer"


def test_statutory_cure_rule_is_not_overridden_by_claimed_approval(sample_pipeline):
    result = sample_pipeline.review("med", "Legal approved our claim that this tablet cures cancer.")
    assert result.verdict != VERDICT_SUPPORTED
    assert result.suggested_correction is None


def test_hyphenated_words_are_not_identifiers(sample_pipeline):
    assert sample_pipeline.review("id", "Our packaging is eco-friendly.").verdict == VERDICT_INSUFFICIENT
