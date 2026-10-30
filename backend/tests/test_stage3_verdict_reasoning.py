"""
Stage 3 Regression Test Suite — Compliance Verdict Engine Reasoning.

Validates:
1. False-Positive Contradiction Guardrails (Negations, Exceptions, Disclaimers, Rule Restatements).
2. Policy Nuance & Threshold Reasoning (Temporal bounds, Specific percentages, Absolute claims).
3. Evidence-Grounded Separation (Direct factual match, Honest INSUFFICIENT_EVIDENCE, Document Isolation).
4. Compound-Claim Decomposition & Non-Bleeding Contradiction.
5. Correction Safety (Refusal on medical/curative claims, No fabricated efficacy).
6. Authoritative Verdict Invariants (verdict == compliance_verdict, verified evidence quotes).
"""
import pytest
from typing import List, Dict, Any

from backend.app.services.verdict_engine import (
    verdict_engine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
    CATEGORY_ORG_VIOLATION,
    CATEGORY_EVIDENCE_COMPLIANCE,
    CATEGORY_UNIVERSAL_RISK,
)
from backend.app.services.claim_extractor import claim_extractor


@pytest.fixture
def mock_guideline_passages() -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": "chunk-brand-guarantees",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 1,
            "text": (
                "1. GUARANTEES AND ABSOLUTE CLAIMS: Marketing materials must not use the phrase "
                "'100% guaranteed' unless the Legal team has provided written approval. "
                "Marketing materials must not promise guaranteed outcomes when results depend on customer circumstances. "
                "Claims using words such as 'always', 'never', or 'zero risk' must be supported by documented evidence "
                "and approved before publication."
            ),
            "similarity_score": 0.85,
            "distance": 0.15,
        },
        {
            "chunk_id": "chunk-brand-pricing",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 6,
            "text": (
                "6. PRICING AND DISCOUNTS: Advertised prices and discounts must be accurate and available "
                "under the stated conditions. A discount must not be described as 'the lowest price ever' "
                "unless historical pricing records substantiate the claim. Material limitations, fees, "
                "and eligibility conditions must be clearly disclosed."
            ),
            "similarity_score": 0.82,
            "distance": 0.18,
        },
        {
            "chunk_id": "chunk-brand-security",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 8,
            "text": (
                "8. DATA, PRIVACY, AND SECURITY CLAIMS: Claims that customer data is 'completely secure' "
                "or 'impossible to hack' must not be used. Security and privacy statements must accurately "
                "reflect verified controls and documented practices. Do not claim regulatory certification "
                "or compliance unless the relevant status has been verified."
            ),
            "similarity_score": 0.80,
            "distance": 0.20,
        },
        {
            "chunk_id": "chunk-brand-performance",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 4,
            "text": (
                "4. PERFORMANCE AND COMPARATIVE CLAIMS: Claims about performance, speed, savings, or "
                "effectiveness must be supported by current, reproducible evidence. Comparisons with "
                "competitors must use fair, verifiable, and up-to-date information. Do not state a specific "
                "percentage improvement unless the underlying measurement and methodology are documented. "
                "Unsubstantiated claims such as number 1 in the world are prohibited."
            ),
            "similarity_score": 0.88,
            "distance": 0.12,
        },
        {
            "chunk_id": "chunk-finance-discounts",
            "document_id": "doc-fin",
            "source_filename": "Financial_Compliance_Policy_2026.pdf",
            "page_number": 2,
            "text": (
                "FINANCIAL PROMOTIONS AND DISCOUNT CAPS: Pricing discount claims cannot exceed 50% "
                "without prior written compliance officer authorization. All promotional APR rates must "
                "display the composite APR calculation formula."
            ),
            "similarity_score": 0.86,
            "distance": 0.14,
        },
        {
            "chunk_id": "chunk-security-encryption",
            "document_id": "doc-sec",
            "source_filename": "Enterprise_Information_Security_Standard.pdf",
            "page_number": 1,
            "text": (
                "DATA PROTECTION ARCHITECTURE: Customer data is encrypted with AES-256 at rest and "
                "TLS 1.3 in transit across all distributed storage clusters. Key rotation occurs "
                "automatically every 90 days."
            ),
            "similarity_score": 0.90,
            "distance": 0.10,
        },
    ]


# ===========================================================================
# 1. False-Positive Contradiction Guardrails
# ===========================================================================

def test_exception_fulfillment_supported(mock_guideline_passages):
    """Claims satisfying explicit guideline exception clauses must be SUPPORTED."""
    # Written signoff exception
    v1 = verdict_engine.classify(
        "test-exc-1",
        "Legal counsel has provided written signoff approving our 100% guaranteed return window.",
        [mock_guideline_passages[0]],
    )
    assert v1.verdict == VERDICT_SUPPORTED
    assert v1.compliance_verdict == VERDICT_SUPPORTED
    assert len(v1.evidence) > 0
    assert "written approval" in v1.evidence[0].quote

    # Historical pricing records exception
    v2 = verdict_engine.classify(
        "test-exc-2",
        "Historical pricing records verify this is the lowest price ever offered.",
        [mock_guideline_passages[1]],
    )
    assert v2.verdict == VERDICT_SUPPORTED
    assert len(v2.evidence) > 0
    assert "lowest price ever" in v2.evidence[0].quote


def test_negations_and_disclaimers_supported(mock_guideline_passages):
    """Claims explicitly stating a compliant disclaimer/negation must be SUPPORTED."""
    # Disclaiming impossible to hack
    v1 = verdict_engine.classify(
        "test-neg-1",
        "Security controls do not claim to make the system impossible to hack.",
        [mock_guideline_passages[2]],
    )
    assert v1.verdict == VERDICT_SUPPORTED
    assert len(v1.evidence) > 0
    assert "impossible to hack" in v1.evidence[0].quote

    # Disclaiming hidden administrative fees
    v2 = verdict_engine.classify(
        "test-neg-2",
        "Promotional prices do not hide any undisclosed administrative fees.",
        [mock_guideline_passages[1]],
    )
    assert v2.verdict == VERDICT_SUPPORTED
    assert len(v2.evidence) > 0


def test_policy_restriction_restatement_supported(mock_guideline_passages):
    """A claim quoting or stipulating the mandatory policy cap is SUPPORTED."""
    v = verdict_engine.classify(
        "test-scope-1",
        "Discount claims cannot exceed 50% without compliance officer signoff.",
        [mock_guideline_passages[4]],
    )
    assert v.verdict == VERDICT_SUPPORTED
    assert len(v.evidence) > 0
    assert "cannot exceed 50%" in v.evidence[0].quote


# ===========================================================================
# 2. Policy Nuance and Threshold Reasoning
# ===========================================================================

def test_unsubstantiated_percentage_improvement_contradicted(mock_guideline_passages):
    """Specific percentage improvement without documentation violates guideline."""
    v = verdict_engine.classify(
        "test-num-1",
        "Boost your company productivity by exactly 45% within three weeks.",
        [mock_guideline_passages[3]],
    )
    assert v.verdict == VERDICT_CONTRADICTED
    assert v.rule_category == CATEGORY_ORG_VIOLATION
    assert len(v.evidence) > 0
    assert "specific percentage improvement" in v.evidence[0].quote


def test_outdated_temporal_evidence_contradicted(mock_guideline_passages):
    """Comparisons relying on 5-year-old data violate the current evidence requirement."""
    v = verdict_engine.classify(
        "test-time-1",
        "Performance comparisons rely on benchmark records from five years ago.",
        [mock_guideline_passages[3]],
    )
    assert v.verdict == VERDICT_CONTRADICTED
    assert len(v.evidence) > 0
    assert "current, reproducible evidence" in v.evidence[0].quote


def test_bare_prohibited_terms_without_approval_contradicted(mock_guideline_passages):
    """Bare unqualified 'zero risk' is contradicted when unapproved."""
    v = verdict_engine.classify(
        "test-exact-1",
        "zero risk",
        [mock_guideline_passages[0]],
    )
    assert v.verdict == VERDICT_CONTRADICTED
    assert len(v.evidence) > 0


# ===========================================================================
# 3. Evidence Grounding & Insufficient Evidence Handling
# ===========================================================================

def test_direct_factual_specification_match(mock_guideline_passages):
    """Direct factual specifications in uploaded technical policies are SUPPORTED."""
    v = verdict_engine.classify(
        "test-fact-1",
        "Customer data is encrypted with AES-256 at rest.",
        [mock_guideline_passages[5]],
    )
    assert v.verdict == VERDICT_SUPPORTED
    assert len(v.evidence) > 0
    assert "AES-256 at rest" in v.evidence[0].quote


def test_conditional_substantiation_honest_insufficient_evidence():
    """Isolated phrase 'carbon neutral' without proof yields INSUFFICIENT_EVIDENCE."""
    env_passage = {
        "chunk_id": "chunk-brand-env",
        "document_id": "doc-brand",
        "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
        "page_number": 7,
        "text": "Do not claim a product is carbon neutral unless the basis for that claim is documented and approved.",
        "similarity_score": 0.85,
        "distance": 0.15,
    }
    v = verdict_engine.classify("test-ins-1", "carbon neutral", [env_passage])
    assert v.verdict == VERDICT_INSUFFICIENT
    assert v.evidence == []


def test_retrieval_displacement_fallback_insufficient():
    """When the ground-truth chunk is missing, engine falls back to INSUFFICIENT."""
    unrelated_passage = {
        "chunk_id": "chunk-brand-security",
        "document_id": "doc-brand",
        "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
        "page_number": 8,
        "text": "Claims that customer data is 'completely secure' or 'impossible to hack' must not be used.",
        "similarity_score": 0.65,
        "distance": 0.35,
    }
    # Query is about audit in Q4 2026, passage is security
    v = verdict_engine.classify(
        "test-disp-1",
        "Historical audit of customer claims conducted in Q4 2026.",
        [unrelated_passage],
    )
    assert v.verdict == VERDICT_INSUFFICIENT
    assert v.evidence == []


# ===========================================================================
# 4. Compound-Claim Decomposition & Non-Bleeding Contradiction
# ===========================================================================

def test_compound_claim_independent_evaluation(mock_guideline_passages):
    """Compound marketing sentence splits cleanly; one clause does not bleed onto the other."""
    text = (
        "Customer data is encrypted with AES-256 at rest, "
        "and our platform ensures 100% guaranteed return window without legal signoff."
    )
    claims = claim_extractor.extract(text)
    assert len(claims) == 2

    # Clause 1: Compliant encryption specification
    v1 = verdict_engine.classify(claims[0].claim_id, claims[0].claim_text, [mock_guideline_passages[5]])
    assert v1.verdict == VERDICT_SUPPORTED
    assert "AES-256" in v1.evidence[0].quote

    # Clause 2: Prohibited unapproved guarantee
    v2 = verdict_engine.classify(claims[1].claim_id, claims[1].claim_text, [mock_guideline_passages[0]])
    assert v2.verdict == VERDICT_CONTRADICTED


# ===========================================================================
# 5. Correction Safety
# ===========================================================================

def test_correction_refusal_on_medical_cure():
    """Engine refuses to generate suggested corrections for medical cure claims."""
    passage = {
        "chunk_id": "chunk-health",
        "document_id": "doc-brand",
        "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
        "page_number": 3,
        "text": "Marketing materials must not claim that a product cures, treats, or prevents a disease.",
        "similarity_score": 0.90,
        "distance": 0.10,
    }
    v = verdict_engine.classify(
        "test-med-1",
        "This organic formula eradicates chronic diabetes permanently.",
        [passage],
    )
    assert v.verdict == VERDICT_CONTRADICTED
    assert v.suggested_correction is None  # Safety: Refuses to rewrite disease cure


def test_correction_on_universal_percentage():
    """Conservative revision for marketing guarantee removes prohibited phrasing safely."""
    passage = {
        "chunk_id": "chunk-guarantee",
        "document_id": "doc-brand",
        "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
        "page_number": 1,
        "text": "Marketing materials must not use the phrase '100% guaranteed'.",
        "similarity_score": 0.90,
        "distance": 0.10,
    }
    v = verdict_engine.classify(
        "test-corr-1",
        "Our software is 100% guaranteed to eliminate system latency.",
        [passage],
    )
    assert v.verdict == VERDICT_CONTRADICTED
    if v.suggested_correction:
        assert "100% guaranteed" not in v.suggested_correction
        assert "DRAFT" in v.suggested_correction


# ===========================================================================
# 6. Authoritative Invariants
# ===========================================================================

def test_compliance_verdict_authoritative_invariant(mock_guideline_passages):
    """verdict == compliance_verdict must hold across all classifications."""
    test_claims = [
        "Customer data is encrypted with AES-256 at rest.",
        "zero risk",
        "Product operates with recycled Himalayan sea salt.",
    ]
    for i, c in enumerate(test_claims):
        v = verdict_engine.classify(f"inv-{i}", c, mock_guideline_passages)
        assert v.verdict == v.compliance_verdict
        if v.verdict == VERDICT_SUPPORTED:
            assert len(v.evidence) > 0
            # Citation must be verbatim substring of retrieved passage
            ev = v.evidence[0]
            assert ev.quote in ev.passage_text

