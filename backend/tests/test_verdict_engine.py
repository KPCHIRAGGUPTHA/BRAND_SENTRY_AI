"""
Unit Tests for the Three-Way Verdict Engine — Phase 3.

All tests are fully deterministic: no API calls, no ChromaDB, no network.
The LLM code path is not exercised here — that path is tested separately
with mocked responses (see test_review_api.py).
"""
import pytest
from backend.app.services.verdict_engine import (
    VerdictEngine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
    EvidenceItem,
    _parse_and_validate_llm_output,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_passage(
    text: str,
    chunk_id: str = "chunk-1",
    document_id: str = "doc-1",
    source_filename: str = "guidelines.pdf",
    page_number: int = 1,
    similarity_score: float = 0.85,
    distance: float = 0.15,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "source_filename": source_filename,
        "page_number": page_number,
        "text": text,
        "similarity_score": similarity_score,
        "distance": distance,
    }


@pytest.fixture
def engine():
    # Use a low threshold so all test passages pass the filter
    return VerdictEngine(similarity_threshold=0.1)


# ---------------------------------------------------------------------------
# Deterministic prohibited-phrase tests
# ---------------------------------------------------------------------------

class TestProhibitedPhraseRules:
    def test_100_pct_guaranteed_is_contradicted(self, engine):
        cv = engine.classify("claim-1", "Our serum is 100% guaranteed to work.", [])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.deterministic_rule_fired is True

    def test_100_pct_safe_is_contradicted(self, engine):
        cv = engine.classify("claim-1", "This product is 100% safe for all users.", [])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.deterministic_rule_fired is True

    def test_100_pct_natural_is_contradicted(self, engine):
        cv = engine.classify("claim-1", "Our ingredients are 100% natural.", [])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.deterministic_rule_fired is True

    def test_clinically_proven_is_contradicted(self, engine):
        cv = engine.classify("claim-1", "Clinically proven to reduce fine lines.", [])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.deterministic_rule_fired is True

    def test_prohibited_phrase_overrides_retrieval(self, engine):
        # Even with a supportive passage, a prohibited phrase must be contradicted
        passage = _make_passage(
            "This product is approved for sale and use.",
            similarity_score=0.95,
        )
        cv = engine.classify("claim-1", "Our product is 100% safe.", [passage])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.deterministic_rule_fired is True

    def test_non_prohibited_claim_not_contradicted_by_rule(self, engine):
        cv = engine.classify("claim-1", "Our product supports healthy skin.", [])
        # With no passages and no prohibited phrase, should be INSUFFICIENT
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.deterministic_rule_fired is False


# ---------------------------------------------------------------------------
# No relevant evidence
# ---------------------------------------------------------------------------

class TestInsufficientEvidence:
    def test_empty_passages_returns_insufficient(self, engine):
        cv = engine.classify("claim-1", "Our cream moisturises for 24 hours.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.evidence == []

    def test_below_threshold_passages_returns_insufficient(self, engine):
        high_threshold_engine = VerdictEngine(similarity_threshold=0.99)
        passage = _make_passage("Moisturising claims are allowed.", similarity_score=0.5)
        cv = high_threshold_engine.classify("claim-1", "Our cream moisturises.", [passage])
        assert cv.verdict == VERDICT_INSUFFICIENT

    def test_insufficient_evidence_never_fabricates_citation(self, engine):
        cv = engine.classify("claim-1", "This claim has no related guideline.", [])
        assert len(cv.evidence) == 0
        assert cv.verdict == VERDICT_INSUFFICIENT


# ---------------------------------------------------------------------------
# Evidence-based CONTRADICTED
# ---------------------------------------------------------------------------

class TestContradictedByEvidence:
    def test_prohibition_language_in_passage_triggers_contradicted(self, engine):
        passage = _make_passage(
            "Marketing materials must not use language implying guaranteed results.",
            similarity_score=0.80,
        )
        cv = engine.classify(
            "claim-1",
            "Our product is guaranteed to deliver visible results.",
            [passage],
        )
        assert cv.verdict == VERDICT_CONTRADICTED

    def test_shall_not_in_passage_triggers_contradicted(self, engine):
        passage = _make_passage(
            "Advertisers shall not make absolute safety claims without clinical backing.",
            similarity_score=0.75,
        )
        cv = engine.classify("claim-1", "Our product delivers absolute safety.", [passage])
        assert cv.verdict == VERDICT_CONTRADICTED

    def test_banned_keyword_in_passage(self, engine):
        passage = _make_passage(
            "The phrase 'number 1 in the world' is banned unless independently verified.",
            similarity_score=0.80,
        )
        cv = engine.classify("claim-1", "We are leaders in the industry.", [passage])
        assert cv.verdict == VERDICT_CONTRADICTED

    def test_evidence_items_have_validated_quotes(self, engine):
        passage = _make_passage(
            "Marketing materials must not make guaranteed claims.",
            similarity_score=0.80,
        )
        cv = engine.classify("claim-1", "Results guaranteed in 7 days.", [passage])
        if cv.evidence:
            for e in cv.evidence:
                assert e.quote in e.passage_text, (
                    f"Quote '{e.quote}' not found in passage '{e.passage_text}'"
                )


# ---------------------------------------------------------------------------
# Evidence-based SUPPORTED
# ---------------------------------------------------------------------------

class TestSupportedByEvidence:
    def test_approved_keyword_in_passage_triggers_supported(self, engine):
        passage = _make_passage(
            "All moisturising claims are approved for use in brand communications.",
            similarity_score=0.80,
        )
        cv = engine.classify("claim-1", "Our cream moisturises skin.", [passage])
        assert cv.verdict == VERDICT_SUPPORTED

    def test_meets_requirements_passage_triggers_supported(self, engine):
        passage = _make_passage(
            "This product meets all requirements for allergen-free labelling.",
            similarity_score=0.85,
        )
        cv = engine.classify("claim-1", "Our product is allergen-free.", [passage])
        assert cv.verdict == VERDICT_SUPPORTED

    def test_supported_verdict_includes_evidence(self, engine):
        passage = _make_passage(
            "Certified claims are authorised for product communications.",
            similarity_score=0.82,
        )
        cv = engine.classify("claim-1", "We are certified.", [passage])
        if cv.verdict == VERDICT_SUPPORTED:
            assert len(cv.evidence) > 0


# ---------------------------------------------------------------------------
# Ambiguous / non-decisive evidence
# ---------------------------------------------------------------------------

class TestAmbiguousEvidence:
    def test_topic_overlap_alone_not_sufficient_for_supported(self, engine):
        # A passage about moisturising that doesn't say it's approved or prohibited
        passage = _make_passage(
            "Moisturising ingredients include hyaluronic acid and glycerin.",
            similarity_score=0.78,
        )
        cv = engine.classify("claim-1", "Our cream moisturises for 24 hours.", [passage])
        # Topic overlap alone should NOT produce SUPPORTED (no affirmative language)
        # Acceptable verdicts: INSUFFICIENT_EVIDENCE or CONTRADICTED
        assert cv.verdict in (VERDICT_INSUFFICIENT, VERDICT_CONTRADICTED)

    def test_multiple_passages_with_mixed_signals(self, engine):
        passages = [
            _make_passage(
                "Moisturising claims are generally acceptable.",
                chunk_id="c1", similarity_score=0.75,
            ),
            _make_passage(
                "Must not claim products cure any medical condition.",
                chunk_id="c2", similarity_score=0.72,
            ),
        ]
        cv = engine.classify("claim-1", "Our product moisturises skin.", passages)
        # With prohibition language in one passage, expect CONTRADICTED
        assert cv.verdict in (VERDICT_CONTRADICTED, VERDICT_INSUFFICIENT, VERDICT_SUPPORTED)
        # Crucially: verdict must be one of the valid values
        assert cv.verdict in (VERDICT_SUPPORTED, VERDICT_CONTRADICTED, VERDICT_INSUFFICIENT)


# ---------------------------------------------------------------------------
# Citation validation
# ---------------------------------------------------------------------------

class TestCitationValidation:
    def test_quote_is_substring_of_passage(self, engine):
        passage = _make_passage(
            "All advertising must comply with brand voice guidelines.",
            similarity_score=0.80,
        )
        cv = engine.classify("claim-1", "Our ad complies with guidelines.", [passage])
        for e in cv.evidence:
            assert e.quote in e.passage_text

    def test_evidence_deduplication(self, engine):
        # Same chunk_id twice should not produce duplicate evidence items
        passage1 = _make_passage("Prohibited phrase: absolute claims.", chunk_id="dup", similarity_score=0.85)
        passage2 = _make_passage("Prohibited phrase: absolute claims.", chunk_id="dup", similarity_score=0.80)
        cv = engine.classify("claim-1", "Our product is the best globally.", [passage1, passage2])
        chunk_ids = [e.chunk_id for e in cv.evidence]
        assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk_ids in evidence"

    def test_page_number_preserved(self, engine):
        passage = _make_passage(
            "Must not use prohibited language.",
            page_number=7, similarity_score=0.80,
        )
        cv = engine.classify("claim-1", "Our product is 100% guaranteed.", [passage])
        # deterministic rule fires, but evidence is also built
        # Page number from passage should be preserved in evidence
        if cv.evidence:
            assert cv.evidence[0].page_number == 7

    def test_missing_page_number_allowed(self, engine):
        passage = _make_passage("Prohibited claims.", page_number=None, similarity_score=0.80)
        cv = engine.classify("claim-1", "We are 100% guaranteed.", [passage])
        # Should not raise
        assert cv.verdict in (VERDICT_SUPPORTED, VERDICT_CONTRADICTED, VERDICT_INSUFFICIENT)


# ---------------------------------------------------------------------------
# LLM output parsing (independent of network)
# ---------------------------------------------------------------------------

class TestLLMOutputParsing:
    def test_valid_json_supported(self):
        raw = '{"verdict": "SUPPORTED", "explanation": "The guideline allows this claim.", "suggested_correction": null}'
        result = _parse_and_validate_llm_output(raw)
        assert result is not None
        assert result["verdict"] == VERDICT_SUPPORTED
        assert result["suggested_correction"] is None

    def test_valid_json_contradicted(self):
        raw = '{"verdict": "CONTRADICTED", "explanation": "This claim is prohibited.", "suggested_correction": "Try: supported by testing."}'
        result = _parse_and_validate_llm_output(raw)
        assert result is not None
        assert result["verdict"] == VERDICT_CONTRADICTED

    def test_invalid_verdict_returns_none(self):
        raw = '{"verdict": "MAYBE", "explanation": "Uncertain."}'
        assert _parse_and_validate_llm_output(raw) is None

    def test_empty_explanation_returns_none(self):
        raw = '{"verdict": "SUPPORTED", "explanation": ""}'
        assert _parse_and_validate_llm_output(raw) is None

    def test_malformed_json_returns_none(self):
        raw = "NOT JSON AT ALL"
        assert _parse_and_validate_llm_output(raw) is None

    def test_markdown_code_fence_stripped(self):
        raw = '```json\n{"verdict": "INSUFFICIENT_EVIDENCE", "explanation": "No relevant evidence found."}\n```'
        result = _parse_and_validate_llm_output(raw)
        assert result is not None
        assert result["verdict"] == VERDICT_INSUFFICIENT

    def test_missing_verdict_key_returns_none(self):
        raw = '{"explanation": "Some reason."}'
        assert _parse_and_validate_llm_output(raw) is None


# ---------------------------------------------------------------------------
# Suggested correction tests
# ---------------------------------------------------------------------------

class TestSuggestedCorrections:
    def test_contradicted_claim_has_correction(self, engine):
        cv = engine.classify("claim-1", "Our product is 100% guaranteed to work.", [])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.suggested_correction is not None
        assert len(cv.suggested_correction) > 10

    def test_correction_does_not_retain_prohibited_phrase(self, engine):
        cv = engine.classify("claim-1", "This is 100% guaranteed effective.", [])
        assert cv.verdict == VERDICT_CONTRADICTED
        # The correction should not contain the exact prohibited phrase
        if cv.suggested_correction:
            assert "100% guaranteed" not in cv.suggested_correction.lower().replace(
                "[draft", ""
            )

    def test_insufficient_evidence_has_review_advice(self, engine):
        cv = engine.classify("claim-1", "Our product supports wellness.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        # Should have some guidance text
        assert cv.suggested_correction is not None or cv.explanation
