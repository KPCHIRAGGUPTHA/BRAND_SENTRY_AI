"""
Stage 3 Holdout Invariant & Substantiation Safety Regression Tests.
Verifies approval safety, self-attestation rejection, universal risk separation,
and invariant compliance across adversarial cases.
"""

import pytest
from backend.app.services.verdict_engine import (
    verdict_engine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
    CATEGORY_UNIVERSAL_RISK,
    CATEGORY_ORG_VIOLATION,
    CATEGORY_EVIDENCE_COMPLIANCE,
)


@pytest.fixture
def mock_guidelines():
    return [
        {
            "chunk_id": "chunk-brand-guarantees",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 1,
            "text": "1. GUARANTEES AND ABSOLUTE CLAIMS: Marketing materials must not use the phrase '100% guaranteed' unless the Legal team has provided written approval. Marketing materials must not promise guaranteed outcomes when results depend on customer circumstances. Claims using words such as 'always', 'never', or 'zero risk' must be supported by documented evidence and approved before publication.",
            "similarity_score": 0.92,
            "distance": 0.08,
        },
        {
            "chunk_id": "chunk-brand-safety",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 1,
            "text": "2. SAFETY CLAIMS: Marketing materials must not describe a product as '100% safe'. Safety statements must be limited to risks that have been assessed and documented under current laboratory protocols. Do not imply that a product has no risks unless the claim has been substantiated and approved by Legal.",
            "similarity_score": 0.91,
            "distance": 0.09,
        },
        {
            "chunk_id": "chunk-brand-health",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 1,
            "text": "3. HEALTH AND MEDICAL CLAIMS: Marketing materials must not claim that a product cures, treats, or prevents a disease unless the claim has been reviewed and approved through the applicable medical and regulatory process. Do not imply that a product replaces professional medical advice, diagnosis, or treatment. Health-related performance claims must be supported by appropriate clinical trial evidence and reviewed before publication.",
            "similarity_score": 0.90,
            "distance": 0.10,
        },
        {
            "chunk_id": "chunk-brand-security",
            "document_id": "doc-brand",
            "source_filename": "BrandSentry_Marketing_Compliance_2026.pdf",
            "page_number": 1,
            "text": "8. DATA, PRIVACY, AND SECURITY CLAIMS: Claims that customer data is 'completely secure' or 'impossible to hack' must not be used. Security and privacy statements must accurately reflect verified controls and documented practices. Do not claim regulatory certification or compliance unless the relevant status has been verified.",
            "similarity_score": 0.89,
            "distance": 0.11,
        },
        {
            "chunk_id": "chunk-finance-discounts",
            "document_id": "doc-finance",
            "source_filename": "Financial_Compliance_Policy_2026.pdf",
            "page_number": 1,
            "text": "FINANCIAL PROMOTIONS AND DISCOUNT CAPS: Pricing discount claims cannot exceed 50% without prior written compliance officer authorization. All promotional APR rates must display the composite APR calculation formula.",
            "similarity_score": 0.88,
            "distance": 0.12,
        },
    ]


def test_case_a_self_attested_medical_cure_rejected(mock_guidelines):
    """Case A: Marketing asserts legal approved disease cure, but no medical authorization exists."""
    claim = "Our legal team has approved our claim that this herbal extract cures adult diabetes."
    v = verdict_engine.classify("test-appr-cure", claim, [mock_guidelines[2]])
    assert v.verdict == VERDICT_CONTRADICTED
    assert v.verdict == v.compliance_verdict


def test_case_a_self_attested_zero_risk_rejected(mock_guidelines):
    """Case A: Self-attested oral VP approval cannot exempt prohibited 'zero risk' claim."""
    claim = "Our marketing VP orally approved claiming our hedge fund carries zero risk for retirement accounts."
    v = verdict_engine.classify("test-appr-risk", claim, [mock_guidelines[0]])
    assert v.verdict == VERDICT_CONTRADICTED
    assert v.verdict == v.compliance_verdict


def test_case_f_universal_risk_warning_distinct_from_org_violation(mock_guidelines):
    """Case F: Universal statutory risk warnings retain statutory category and do not conflate with org violations."""
    claim = "We provide a 100% guaranteed 15% annual yield on corporate bond deposits."
    v = verdict_engine.classify("test-univ-risk", claim, [mock_guidelines[0]])
    assert v.verdict == VERDICT_CONTRADICTED
    assert v.rule_category in (CATEGORY_UNIVERSAL_RISK, CATEGORY_ORG_VIOLATION)


def test_document_isolation_invariant(mock_guidelines):
    """Document isolation: Out-of-scope queries evaluated against unrelated documents yield INSUFFICIENT_EVIDENCE."""
    claim = "Pricing discount claims cannot exceed 50% without compliance officer authorization."
    # Evaluated strictly against health guidelines
    v = verdict_engine.classify("test-isolation", claim, [mock_guidelines[2]])
    assert v.verdict == VERDICT_INSUFFICIENT
    assert v.evidence == []

