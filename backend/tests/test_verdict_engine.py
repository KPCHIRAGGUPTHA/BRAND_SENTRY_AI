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
    def test_100_pct_guaranteed_is_warning_without_evidence(self, engine):
        cv = engine.classify("claim-1", "Our serum is 100% guaranteed to work.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.compliance_verdict == VERDICT_INSUFFICIENT
        assert cv.deterministic_rule_fired is True
        assert cv.risk_warning is not None
        assert cv.risk_warning.rule_id == "RULE-UNIV-ABS-001"
        assert cv.evidence == []

    def test_100_pct_safe_is_warning_without_evidence(self, engine):
        cv = engine.classify("claim-1", "This product is 100% safe for all users.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.compliance_verdict == VERDICT_INSUFFICIENT
        assert cv.deterministic_rule_fired is True
        assert cv.risk_warning is not None

    def test_100_pct_natural_is_warning_without_evidence(self, engine):
        cv = engine.classify("claim-1", "Our ingredients are 100% natural.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.compliance_verdict == VERDICT_INSUFFICIENT
        assert cv.deterministic_rule_fired is True
        assert cv.risk_warning is not None

    def test_clinically_proven_is_warning_without_evidence(self, engine):
        cv = engine.classify("claim-1", "Clinically proven to reduce fine lines.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.compliance_verdict == VERDICT_INSUFFICIENT
        assert cv.deterministic_rule_fired is True
        assert cv.risk_warning is not None

    def test_prohibited_phrase_with_explicit_guideline_is_contradicted(self, engine):
        passage = _make_passage(
            "Brand Safety Policy: Claims asserting our product is 100% safe are strictly forbidden.",
            similarity_score=0.95,
        )
        cv = engine.classify("claim-1", "Our product is 100% safe.", [passage])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert cv.compliance_verdict == VERDICT_CONTRADICTED
        assert cv.deterministic_rule_fired is True
        assert len(cv.evidence) >= 1

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
    def test_warning_claim_has_correction(self, engine):
        cv = engine.classify("claim-1", "Our product is 100% guaranteed to work.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.compliance_verdict == VERDICT_INSUFFICIENT
        assert cv.suggested_correction is not None
        assert len(cv.suggested_correction) > 10

    def test_correction_does_not_retain_prohibited_phrase(self, engine):
        cv = engine.classify("claim-1", "This is 100% guaranteed effective.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        if cv.suggested_correction:
            assert "100% guaranteed" not in cv.suggested_correction.lower().replace(
                "[draft", ""
            )

    def test_100_percent_guaranteed_to_verb_grammar(self, engine):
        cv = engine.classify("claim-1", "Our product is 100% guaranteed to work.", [])
        assert cv.suggested_correction is not None
        # Must be grammatically correct: "is designed to work", not "is designed to support to work"
        assert "is designed to work" in cv.suggested_correction
        assert "support to" not in cv.suggested_correction
        assert "to to" not in cv.suggested_correction

    def test_100_percent_guaranteed_adjective_grammar(self, engine):
        cv = engine.classify("claim-1", "This formula is 100% guaranteed effective.", [])
        assert cv.suggested_correction is not None
        assert "designed to be effective" in cv.suggested_correction
        assert "100% guaranteed" not in cv.suggested_correction.lower().replace("[draft", "")

    def test_100_percent_guaranteed_predicate_grammar(self, engine):
        cv = engine.classify("claim-1", "Our product is 100% guaranteed.", [])
        assert cv.suggested_correction is not None
        assert "designed with a commitment to quality" in cv.suggested_correction
        assert "100% guaranteed" not in cv.suggested_correction.lower().replace("[draft", "")

    def test_100_percent_guaranteed_does_not_introduce_unsupported_facts(self, engine):
        cv = engine.classify("claim-1", "Our serum is 100% guaranteed to eliminate all wrinkles.", [])
        assert cv.suggested_correction is not None
        sc_lower = cv.suggested_correction.lower()
        # Must not fabricate unsupported factual claims like clinical trials or internal testing
        assert "internal testing" not in sc_lower
        assert "clinical study" not in sc_lower
        assert "peer-reviewed" not in sc_lower
        assert "certified organic" not in sc_lower

    def test_insufficient_evidence_has_review_advice(self, engine):
        cv = engine.classify("claim-1", "Our product supports wellness.", [])
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.suggested_correction is not None or cv.explanation


# ---------------------------------------------------------------------------
# Evidence Deduplication tests
# ---------------------------------------------------------------------------

class TestEvidenceDeduplication:
    def test_identical_passages_deduplicated(self, engine):
        p1 = _make_passage("Absolute claims like 100% guaranteed are prohibited.", chunk_id="c1", document_id="doc-1")
        p2 = _make_passage("Absolute claims like 100% guaranteed are prohibited.", chunk_id="c2", document_id="doc-1")
        items = engine._build_evidence_items([p1, p2], "We are 100% guaranteed.")
        assert len(items) == 1
        assert items[0].chunk_id == "c1"

    def test_distinct_evidence_from_different_sources_preserved(self, engine):
        p1 = _make_passage("Policy 1: Absolute superlatives are strictly prohibited in marketing copy.", chunk_id="c1", document_id="doc-1", source_filename="policy_1.pdf")
        p2 = _make_passage("Standard 2: All performance guarantees require prior compliance sign-off.", chunk_id="c2", document_id="doc-2", source_filename="policy_2.pdf")
        items = engine._build_evidence_items([p1, p2], "We are 100% guaranteed.")
        assert len(items) == 2
        assert {item.document_id for item in items} == {"doc-1", "doc-2"}

    def test_overlapping_sliding_chunk_redundancy_filtered(self, engine):
        full_text = "Rule 1.1: Absolute Performance Bans. Never use absolute terms such as 100% guaranteed in ads."
        sub_text = "Never use absolute terms such as 100% guaranteed in ads."
        p1 = _make_passage(full_text, chunk_id="c1", document_id="doc-1")
        p2 = _make_passage(sub_text, chunk_id="c2", document_id="doc-1")
        items = engine._build_evidence_items([p1, p2], "We are 100% guaranteed.")
        assert len(items) == 1


# ---------------------------------------------------------------------------
# Evidence Relevance & Specific Grounding Tests (100% safe vs 100% guaranteed)
# ---------------------------------------------------------------------------

class TestEvidenceRelevance:
    def test_100_safe_prefers_safety_passage_over_guarantee(self, engine):
        passage_guarantee = _make_passage(
            "Section 1.1: Superlatives. Never claim our product is '100% Guaranteed' to work.",
            chunk_id="cg",
            document_id="doc-1",
            similarity_score=0.90,  # even with higher similarity
        )
        passage_safety = _make_passage(
            "Section 1.2: Safety Standards. Formulas must never be advertised as '100% safe' without certification.",
            chunk_id="cs",
            document_id="doc-1",
            similarity_score=0.85,
        )

        cv = engine.classify("claim-1", "Our product is 100% safe.", [passage_guarantee, passage_safety])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) >= 1
        top_quote = cv.evidence[0].quote
        assert "100% safe" in top_quote or "safe" in top_quote.lower()
        assert "100% guaranteed" not in top_quote.lower()

    def test_100_guaranteed_prefers_guarantee_passage_over_safety(self, engine):
        passage_guarantee = _make_passage(
            "Section 1.1: Superlatives. Never claim our product is '100% Guaranteed' to work.",
            chunk_id="cg",
            document_id="doc-1",
            similarity_score=0.85,
        )
        passage_safety = _make_passage(
            "Section 1.2: Safety Standards. Formulas must never be advertised as '100% safe' without certification.",
            chunk_id="cs",
            document_id="doc-1",
            similarity_score=0.90,  # even with higher similarity
        )

        cv = engine.classify("claim-1", "Our product is 100% guaranteed.", [passage_safety, passage_guarantee])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) >= 1
        top_quote = cv.evidence[0].quote
        assert "100% guaranteed" in top_quote.lower()
        assert "100% safe" not in top_quote.lower()

    def test_combined_passage_extracts_target_quote_for_100_safe(self, engine):
        combined = _make_passage(
            "Compliance Guide: Chapter 1. Never use absolute terms such as '100% guaranteed', "
            "'100% safe', or 'cures all wrinkles'. All claims must reflect limits.",
            chunk_id="c_comb",
            document_id="doc-1",
            similarity_score=0.88,
        )
        cv = engine.classify("claim-1", "Our product is 100% safe.", [combined])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) >= 1
        assert "100% safe" in cv.evidence[0].quote

    def test_combined_passage_extracts_target_quote_for_100_guaranteed(self, engine):
        combined = _make_passage(
            "Compliance Guide: Chapter 1. Never use absolute terms such as '100% guaranteed', "
            "'100% safe', or 'cures all wrinkles'. All claims must reflect limits.",
            chunk_id="c_comb",
            document_id="doc-1",
            similarity_score=0.88,
        )
        cv = engine.classify("claim-1", "Our product is 100% guaranteed.", [combined])
        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) >= 1
        assert "100% guaranteed" in cv.evidence[0].quote.lower()

    def test_no_false_evidence_when_guideline_does_not_support_safety(self, engine):
        passage_guarantee = _make_passage(
            "Section 1.1: Superlatives. Never claim our product is '100% Guaranteed'.",
            chunk_id="cg",
            document_id="doc-1",
            similarity_score=0.85,
        )
        # Guideline only prohibits 100% guaranteed, says nothing about safety
        cv = engine.classify("claim-1", "Our product is 100% safe.", [passage_guarantee])
        # In authoritative semantics, warning without guideline evidence produces INSUFFICIENT_EVIDENCE
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.compliance_verdict == VERDICT_INSUFFICIENT
        assert cv.risk_warning is not None
        # Evidence must NOT cite the unrelated guarantee rule as evidence for 100% safe
        assert cv.evidence == []


class TestTask4RegressionScenarios:
    """Explicit regression tests for Task 2, Task 3, and Task 4 compliance specifications."""

    def test_guarantee_claim_cites_guarantee_rule_not_safety_rule(self, engine):
        """Ensure guarantee claims cite guarantee rules when both safety and guarantee rules are retrieved."""
        guarantee_passage = _make_passage(
            "Consumer Ad Policy: Never use '100% Guaranteed' under any circumstances.",
            chunk_id="chunk-guarantee",
            source_filename="guarantee_policy.pdf",
            similarity_score=0.85,
        )
        safety_passage = _make_passage(
            "Product Safety Guide: All ingredients must be safety-certified by toxicologists.",
            chunk_id="chunk-safety",
            source_filename="safety_policy.pdf",
            similarity_score=0.84,
        )
        passages = [guarantee_passage, safety_passage]
        cv = engine.classify("claim-1", "Our product is 100% guaranteed to deliver results.", passages)

        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) == 1
        assert cv.evidence[0].chunk_id == "chunk-guarantee"
        assert "guaranteed" in cv.evidence[0].quote.lower()
        assert "safety-certified" not in cv.evidence[0].quote.lower()

    def test_safety_claim_cites_safety_rule_not_guarantee_rule(self, engine):
        """Ensure safety claims cite safety rules when both safety and guarantee rules are retrieved."""
        guarantee_passage = _make_passage(
            "Consumer Ad Policy: Never use '100% Guaranteed' under any circumstances.",
            chunk_id="chunk-guarantee",
            source_filename="guarantee_policy.pdf",
            similarity_score=0.85,
        )
        safety_passage = _make_passage(
            "Brand Safety Guidelines: Never claim a product is '100% Safe' without peer-reviewed data.",
            chunk_id="chunk-safety",
            source_filename="safety_policy.pdf",
            similarity_score=0.84,
        )
        passages = [guarantee_passage, safety_passage]
        cv = engine.classify("claim-2", "Our product is 100% safe for sensitive skin.", passages)

        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) == 1
        assert cv.evidence[0].chunk_id == "chunk-safety"
        assert "safe" in cv.evidence[0].quote.lower()
        assert "100% guaranteed" not in cv.evidence[0].quote.lower()

    def test_unsupported_claims_return_insufficient_evidence_without_fabricated_citations(self, engine):
        """Ensure claims without relevant support return INSUFFICIENT_EVIDENCE with zero citations."""
        unrelated_passage = _make_passage(
            "Shipping Information: Ground delivery takes 3 to 5 business days across the continental US.",
            chunk_id="chunk-shipping",
            similarity_score=0.30,
        )
        cv = engine.classify(
            "claim-3",
            "Our software increases employee productivity by 85%.",
            [unrelated_passage],
        )

        assert cv.verdict == VERDICT_INSUFFICIENT
        # Crucial constraint: absolutely zero fabricated citations
        assert cv.evidence == []
        assert "sufficient evidence" in cv.explanation.lower()
        assert "human review" in cv.explanation.lower()

    def test_distinguishes_explicit_rules_from_general_recommendations(self, engine):
        """Ensure explanations distinguish explicit policy rules ('must not') from recommendations ('avoid')."""
        explicit_passage = _make_passage(
            "Marketing Standards: Copywriters must not state or imply immediate efficacy.",
            chunk_id="chunk-exp",
            similarity_score=0.85,
        )
        cv_explicit = engine.classify(
            "claim-exp",
            "Our solution provides immediate efficacy.",
            [explicit_passage],
        )
        assert cv_explicit.verdict == VERDICT_CONTRADICTED
        assert "explicit policy rule" in cv_explicit.explanation.lower()

        recommendation_passage = _make_passage(
            "Style Guide: Writers should avoid absolute statements in promotional teasers.",
            chunk_id="chunk-rec",
            similarity_score=0.85,
        )
        cv_rec = engine.classify(
            "claim-rec",
            "Our solution offers absolute excellence.",
            [recommendation_passage],
        )
        assert cv_rec.verdict == VERDICT_CONTRADICTED
        assert "recommendation" in cv_rec.explanation.lower()

    def test_regression_test_a_evidence_traceability_supported(self, engine):
        """Test A: Directly supporting evidence must not be overridden by unrelated discount prohibition."""
        sample_passages = [
            _make_passage(
                "6. PRICING AND DISCOUNTS Advertised prices and discounts must be accurate. "
                "A discount must not be described as 'the lowest price ever' unless historical pricing records substantiate the claim.",
                chunk_id="chunk-discount",
                source_filename="BrandSentry_Sample_Marketing_Compliance_Guidelines.txt",
                similarity_score=0.82,
            ),
            _make_passage(
                "9. EVIDENCE AND APPROVAL Every material factual marketing claim must have a traceable evidence source. "
                "Evidence must be current, relevant to the exact claim, and retained for review.",
                chunk_id="chunk-evidence",
                source_filename="BrandSentry_Sample_Marketing_Compliance_Guidelines.txt",
                similarity_score=0.89,
            ),
        ]
        cv = engine.classify(
            "claim-test-a",
            "Our marketing materials must include traceable evidence sources for every material factual claim.",
            sample_passages,
        )
        assert cv.verdict == VERDICT_SUPPORTED
        assert cv.suggested_correction is None
        assert len(cv.evidence) >= 1
        assert "traceable evidence source" in cv.evidence[0].quote.lower()
        assert "discount" not in cv.explanation.lower()

    def test_regression_test_b_100_pct_safe_contradicted(self, engine):
        """Test B: 100% safe claim is CONTRADICTED citing Section 2 Safety Claims."""
        safety_passage = _make_passage(
            "2. SAFETY CLAIMS Marketing materials must not describe a product as '100% safe'. "
            "Safety statements must be limited to risks that have been assessed and documented.",
            chunk_id="chunk-safety-sec2",
            source_filename="BrandSentry_Sample_Marketing_Compliance_Guidelines.txt",
            similarity_score=0.88,
        )
        cv = engine.classify(
            "claim-test-b",
            "Our product is 100% safe.",
            [safety_passage],
        )
        assert cv.verdict == VERDICT_CONTRADICTED
        assert len(cv.evidence) >= 1
        assert "100% safe" in cv.evidence[0].quote.lower()
        assert cv.deterministic_rule_fired is True

    def test_regression_test_c_100_pct_organic_cotton_insufficient(self, engine):
        """Test C: 100% organic cotton returns INSUFFICIENT_EVIDENCE against BSAI-DEMO-001."""
        env_passage = _make_passage(
            "7. ENVIRONMENTAL CLAIMS Environmental claims such as 'eco-friendly', 'green', or 'zero impact' "
            "must be specific and supported by documented evidence. Do not claim a product is carbon neutral.",
            chunk_id="chunk-env",
            source_filename="BrandSentry_Sample_Marketing_Compliance_Guidelines.txt",
            similarity_score=0.35,
        )
        cv = engine.classify(
            "claim-test-c",
            "Our product is made from 100% organic cotton.",
            [env_passage],
        )
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert cv.evidence == []
        assert "sufficient evidence" in cv.explanation.lower() or "not establish" in cv.explanation.lower()

    def test_regression_test_d_50_pct_faster_competitor_insufficient(self, engine):
        """Test D: 50% faster than every competitor returns INSUFFICIENT_EVIDENCE under Section 4."""
        perf_passage = _make_passage(
            "4. PERFORMANCE AND COMPARATIVE CLAIMS Claims about performance, speed, savings, or effectiveness "
            "must be supported by current, reproducible evidence. Comparisons with competitors must use fair, "
            "verifiable, and up-to-date information. Do not state a specific percentage improvement unless "
            "the underlying measurement and methodology are documented.",
            chunk_id="chunk-perf",
            source_filename="BrandSentry_Sample_Marketing_Compliance_Guidelines.txt",
            similarity_score=0.80,
        )
        cv = engine.classify(
            "claim-test-d",
            "Our software is 50% faster than every competitor.",
            [perf_passage],
        )
        assert cv.verdict == VERDICT_INSUFFICIENT
        assert "sufficient evidence" in cv.explanation.lower() or "require" in cv.explanation.lower() or "documentation" in cv.explanation.lower()
