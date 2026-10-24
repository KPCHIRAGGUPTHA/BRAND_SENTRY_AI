"""
Automated Test Suite for Semantic Drift Detection in BrandSentry AI.

Verifies:
1. Category coverage:
   - CERTAINTY_SHIFT (Example A)
   - SCOPE_EXPANSION (Example B)
   - NUMERICAL_EXAGGERATION (Example C)
   - CONDITION_OMISSION (Example D)
   - TEMPORAL_SHIFT
   - CAUSALITY_SHIFT
   - COMPARISON_SHIFT
2. Edge cases & guardrails:
   - Claim with no meaningful semantic drift
   - Empty/missing evidence handling
   - Unrelated claim without fabricated findings
   - Uncertainty indicator when evidence is inadequate
3. End-to-end integration:
   - Integration with VerdictEngine
   - Backward compatibility of Review API response schemas
"""

import pytest
from backend.app.services.semantic_drift import (
    SemanticDriftDetector,
    semantic_drift_detector,
)
from backend.app.services.verdict_engine import (
    verdict_engine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
)
from backend.app.schemas.review import (
    ClaimVerdictSchema,
    ReviewResponse,
    ReviewSummary,
    SemanticDriftResult,
)


def _make_passage(text: str, score: float = 0.85, doc_id: str = "doc-1", chunk_id: str = "c-1"):
    return {
        "text": text,
        "similarity_score": score,
        "distance": 1.0 - score,
        "document_id": doc_id,
        "chunk_id": chunk_id,
        "source_filename": "Test_Guidelines.txt",
        "page_number": 1,
    }


class TestSemanticDriftCategories:
    """Tests for each of the 7 semantic drift categories."""

    def test_example_a_certainty_shift(self):
        """
        Example A:
        Source: "Our product may improve productivity under suitable conditions."
        Claim:  "Our product always improves productivity."
        Expected: Detect increased certainty from 'may' to 'always'.
        """
        source = "Our product may improve productivity under suitable conditions."
        claim = "Our product always improves productivity."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        assert len(res.issues) >= 1
        issue = next((i for i in res.issues if i.category == "CERTAINTY_SHIFT"), None)
        assert issue is not None
        assert issue.severity == "HIGH"
        assert "always" in issue.claim_phrase.lower()
        assert "may" in issue.source_phrase.lower() or "suitable conditions" in issue.source_phrase.lower()
        assert issue.suggested_correction is not None
        assert "may" in issue.suggested_correction.lower()

    def test_example_b_scope_expansion(self):
        """
        Example B:
        Source: "The policy applies to registered enterprise customers."
        Claim:  "The policy applies to all customers."
        Expected: Detect expansion of scope from registered enterprise to all customers.
        """
        source = "The policy applies to registered enterprise customers."
        claim = "The policy applies to all customers."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        issue = next((i for i in res.issues if i.category == "SCOPE_EXPANSION"), None)
        assert issue is not None
        assert issue.severity == "HIGH"
        assert "all" in issue.claim_phrase.lower()
        assert "registered enterprise" in issue.source_phrase.lower()

    def test_example_c_numerical_exaggeration(self):
        """
        Example C:
        Source: "Our product improved productivity by up to 15% in an internal test."
        Claim:  "Our product improves productivity by 85% for every customer."
        Expected: Detect the numerical increase (15% -> 85%) and scope expansion.
        """
        source = "Our product improved productivity by up to 15% in an internal test."
        claim = "Our product improves productivity by 85% for every customer."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        num_issue = next((i for i in res.issues if i.category == "NUMERICAL_EXAGGERATION"), None)
        assert num_issue is not None
        assert num_issue.severity == "HIGH"
        assert "85%" in num_issue.claim_phrase
        assert "15%" in num_issue.explanation
        assert "85%" in num_issue.explanation

    def test_example_d_condition_omission(self):
        """
        Example D:
        Source: "Refunds are available within 30 days when the product is unused."
        Claim:  "Refunds are available within 30 days."
        Expected: Flag missing unused-product condition.
        """
        source = "Refunds are available within 30 days when the product is unused."
        claim = "Refunds are available within 30 days."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        cond_issue = next((i for i in res.issues if i.category == "CONDITION_OMISSION"), None)
        assert cond_issue is not None
        assert "unused" in cond_issue.source_phrase.lower()
        assert "omits" in cond_issue.explanation.lower()

    def test_temporal_shift_duration_inflation(self):
        """Detect change in time period (e.g. 30 days vs 60 days)."""
        source = "Product warranty claims are processed within 30 days of submission."
        claim = "Product warranty claims are processed within 60 days of submission."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        temp_issue = next((i for i in res.issues if i.category == "TEMPORAL_SHIFT"), None)
        assert temp_issue is not None
        assert "60 days" in temp_issue.claim_phrase.lower()
        assert "30 days" in temp_issue.source_phrase.lower()

    def test_temporal_shift_instant_turnaround(self):
        """Detect instant turnaround promise against standard turnaround timeframe."""
        source = "Account verification is completed within 3 business days."
        claim = "Account verification is completed instantly."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        temp_issue = next((i for i in res.issues if i.category == "TEMPORAL_SHIFT"), None)
        assert temp_issue is not None
        assert "instantly" in temp_issue.claim_phrase.lower()

    def test_causality_shift(self):
        """Detect upgrading correlation / association to proven causation."""
        source = "Our formula was associated with improved hydration in clinical tests."
        claim = "Our formula causes improved hydration."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        causal_issue = next((i for i in res.issues if i.category == "CAUSALITY_SHIFT"), None)
        assert causal_issue is not None
        assert "causes" in causal_issue.claim_phrase.lower()
        assert "associated with" in causal_issue.source_phrase.lower()

    def test_comparison_shift(self):
        """Detect aggressive superlative comparison not supported by evidence."""
        source = "Our analytics engine is comparable to existing market solutions."
        claim = "Our analytics engine is the fastest in the market."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is True
        comp_issue = next((i for i in res.issues if i.category == "COMPARISON_SHIFT"), None)
        assert comp_issue is not None
        assert "fastest" in comp_issue.claim_phrase.lower()


class TestSemanticDriftEdgeCases:
    """Edge cases, guardrails, and uncertainty handling."""

    def test_no_semantic_drift_detected_on_aligned_claim(self):
        """An aligned claim that respects the evidence should report no drift."""
        source = "Our product may improve productivity by up to 15% under suitable conditions."
        claim = "Our product may improve productivity by up to 15% under suitable conditions."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source)])

        assert res.detected is False
        assert len(res.issues) == 0
        assert res.uncertainty is None

    def test_empty_claim_returns_uncertainty(self):
        """Empty claim text safely returns uncertainty without crashing."""
        res = semantic_drift_detector.analyze("", [_make_passage("Some policy text.")])
        assert res.detected is False
        assert res.uncertainty is not None

    def test_empty_evidence_passages_returns_uncertainty(self):
        """When no passages are retrieved, returns uncertainty instead of inventing findings."""
        res = semantic_drift_detector.analyze("Our product always works.", [])
        assert res.detected is False
        assert len(res.issues) == 0
        assert "No evidence passages available" in res.uncertainty

    def test_unrelated_claim_does_not_fabricate_drift(self):
        """
        Claim discussing organic cotton against a refund policy must NOT
        fabricate a condition or certainty shift.
        """
        source = "Refunds are processed within 14 days with an official receipt."
        claim = "Our apparel uses 100% certified organic cotton."

        res = semantic_drift_detector.analyze(claim, [_make_passage(source, score=0.05)])

        assert res.detected is False
        assert len(res.issues) == 0


class TestVerdictEngineIntegration:
    """Verifies that VerdictEngine correctly incorporates SemanticDriftResult."""

    def test_verdict_engine_attaches_semantic_drift(self):
        """VerdictEngine.classify produces ClaimVerdict with populated semantic_drift field."""
        source_passage = _make_passage(
            "Every material factual marketing claim must have a traceable evidence source.",
            score=0.90,
            doc_id="doc-guideline",
            chunk_id="chunk-evidence",
        )
        claim_text = "Our marketing materials must include traceable evidence sources for every material factual claim."

        cv = verdict_engine.classify("claim-1", claim_text, [source_passage])

        assert cv.verdict == VERDICT_SUPPORTED
        assert cv.semantic_drift is not None
        assert isinstance(cv.semantic_drift, SemanticDriftResult)
        assert cv.semantic_drift.detected is False

    def test_verdict_engine_drift_detected_on_exaggeration(self):
        """Exaggerated claim receives semantic drift findings while retaining proper verdict."""
        source_passage = _make_passage(
            "4. PERFORMANCE Claims about speed must not exceed measured benchmark results of 15%.",
            score=0.85,
            doc_id="doc-perf",
            chunk_id="chunk-perf",
        )
        claim_text = "Our software improves speed by 85%."

        cv = verdict_engine.classify("claim-2", claim_text, [source_passage])

        assert cv.semantic_drift is not None
        assert cv.semantic_drift.detected is True
        num_issue = next((i for i in cv.semantic_drift.issues if i.category == "NUMERICAL_EXAGGERATION"), None)
        assert num_issue is not None
        assert "85%" in num_issue.claim_phrase

    def test_backward_compatibility_schema_serialization(self):
        """Ensure ClaimVerdictSchema and ReviewResponse serialize cleanly with and without semantic_drift."""
        # Without semantic_drift (legacy payload)
        legacy_claim = ClaimVerdictSchema(
            claim_id="claim-legacy",
            claim_text="Sample legacy claim.",
            verdict="SUPPORTED",
            explanation="Legacy explanation.",
            evidence=[],
        )
        assert legacy_claim.semantic_drift is None
        json_data = legacy_claim.model_dump()
        assert "semantic_drift" in json_data
        assert json_data["semantic_drift"] is None

        # With semantic_drift
        drift_claim = ClaimVerdictSchema(
            claim_id="claim-new",
            claim_text="Sample new claim.",
            verdict="CONTRADICTED",
            explanation="Contradicted explanation.",
            evidence=[],
            semantic_drift=SemanticDriftResult(
                detected=True,
                issues=[],
                uncertainty=None,
            ),
        )
        assert drift_claim.semantic_drift is not None
        assert drift_claim.semantic_drift.detected is True
