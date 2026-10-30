"""
Stage 3.5 Targeted Compliance Safety Hardening Regression Tests.

Verifies:
1. Exact identifier and specification validation (matching, mismatching, missing, multiple).
2. Distinguishing policy restatement and operational instructions from prohibited commercial claims.
3. Documentary evidence and approval verification (self-reported approval, unattached files, statutory precedence).
4. Policy nuance handling (compound claims with violations, approximate vs exact numbers).
"""
import pytest
from backend.app.services.verdict_engine import (
    VerdictEngine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
    EvidenceItem,
)


def _make_passage(
    text: str,
    chunk_id: str = "chunk-01",
    doc_name: str = "BrandSentry_Sample_Marketing_Compliance_Guidelines.txt",
    sim: float = 0.82,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "source_filename": doc_name,
        "similarity_score": sim,
        "distance": 0.18,
    }


@pytest.fixture
def engine():
    return VerdictEngine()


class TestTask1ExactIdentifierValidation:
    """Verifies that exact alphanumeric codes and specifications are compared by value, not format."""

    def test_matching_identifier_supported(self, engine):
        passage = _make_passage(
            "All financial advertising materials must display the verified registration code 9845-A on the title page."
        )
        verdict = engine.classify(
            "test-id-1",
            "Our corporate brochure displays verified registration code 9845-A on the title page.",
            [passage],
        )
        assert verdict.verdict == VERDICT_SUPPORTED
        assert "9845-A" in verdict.explanation or len(verdict.evidence) > 0

    def test_mismatching_identifier_not_supported(self, engine):
        passage = _make_passage(
            "All financial advertising materials must display the verified registration code 9845-A on the title page."
        )
        verdict = engine.classify(
            "test-id-2",
            "Our corporate brochure displays registration code 4412-K on the title page.",
            [passage],
        )
        # 4412-K does not match 9845-A -> Must NEVER be SUPPORTED
        assert verdict.verdict != VERDICT_SUPPORTED
        assert verdict.verdict == VERDICT_INSUFFICIENT

    def test_omitted_identifier_contradicted(self, engine):
        passage = _make_passage(
            "Commercial flyers must include state compliance authorization code holdout-reg-101 in 8pt font."
        )
        verdict = engine.classify(
            "test-id-3",
            "Regional distribution fliers intentionally omit regulatory code holdout-reg-101 to conserve visual space.",
            [passage],
        )
        assert verdict.verdict == VERDICT_CONTRADICTED

    def test_cross_product_or_different_spec_rejected(self, engine):
        passage = _make_passage(
            "Enterprise encryption gateways must implement TLS 1.3 across all perimeter termination endpoints."
        )
        verdict = engine.classify(
            "test-id-4",
            "Internal legacy systems terminate inbound connections using TLS 1.0.",
            [passage],
        )
        assert verdict.verdict == VERDICT_INSUFFICIENT or verdict.verdict == VERDICT_CONTRADICTED


class TestTask2PolicyRestatementAndOperationalContext:
    """Verifies that compliance directives, warnings, and internal workplace instructions do not trigger false violations."""

    def test_policy_requirement_restatement_not_prohibited(self, engine):
        passage = _make_passage(
            "Marketing materials must not promise guaranteed outcomes when results depend on customer circumstances."
        )
        verdict = engine.classify(
            "test-restatement-1",
            "Marketing materials must not promise guaranteed outcomes when results depend on customer circumstances.",
            [passage],
        )
        # Repeating the prohibition as a compliance directive must not be classified as making a prohibited guarantee
        assert verdict.verdict in (VERDICT_SUPPORTED, VERDICT_INSUFFICIENT)
        assert verdict.verdict != VERDICT_CONTRADICTED

    def test_internal_workplace_safety_instruction_safe(self, engine):
        passage = _make_passage(
            "1. BRAND LOGO AND VISUAL IDENTITY The BrandSentry emblem must always appear with at least 20px clear space. "
            "Never alter the proportions or color palette."
        )
        verdict = engine.classify(
            "test-ops-1",
            "Warehouse personnel must wear high-visibility orange safety vests while operating forklifts in loading bays.",
            [passage],
        )
        # Irrelevant workplace safety instruction retrieved against brand guidelines must not contradict
        assert verdict.verdict == VERDICT_INSUFFICIENT

    def test_internal_hr_confidentiality_instruction_safe(self, engine):
        passage = _make_passage(
            "6. SECURITY AND PRIVACY CLAIMS Do not state that customer data is completely secure or impossible to hack."
        )
        verdict = engine.classify(
            "test-ops-2",
            "Our human resources department guarantees 100% confidentiality during grievance hearings.",
            [passage],
        )
        # Internal HR procedure retrieved against commercial IT security policy must be INSUFFICIENT_EVIDENCE
        assert verdict.verdict == VERDICT_INSUFFICIENT

    def test_compliant_health_disclaimer_not_violation(self, engine):
        passage = _make_passage(
            "5. HEALTH, SAFETY, AND ENVIRONMENTAL CLAIMS Materials must not claim a product cures or treats a disease."
        )
        verdict = engine.classify(
            "test-disclaimer-1",
            "Our dietary beverage does not cure, treat, or prevent cardiovascular disease.",
            [passage],
        )
        assert verdict.verdict in (VERDICT_SUPPORTED, VERDICT_INSUFFICIENT)
        assert verdict.verdict != VERDICT_CONTRADICTED


class TestTask3DocumentaryEvidenceAndApprovalSafety:
    """Verifies that self-attestation is not proof, unattached records yield INSUFFICIENT, and statutory rules override."""

    def test_self_reported_approval_unattached_insufficient(self, engine):
        passage = _make_passage(
            "2. PROMOTIONAL PRICING AND DISCOUNTS Claims of discounts cannot exceed 50% without written approval "
            "from the compliance officer."
        )
        verdict = engine.classify(
            "test-appr-1",
            "Management confirmed that legal approved our 65% storewide discount, though no authorization file was attached.",
            [passage],
        )
        assert verdict.verdict == VERDICT_INSUFFICIENT

    def test_unattached_archive_evidence_insufficient(self, engine):
        passage = _make_passage(
            "5. HEALTH, SAFETY, AND ENVIRONMENTAL CLAIMS Avoid broad environmental claims such as eco-friendly. "
            "Claims must have a documented and verified basis."
        )
        verdict = engine.classify(
            "test-miss-1",
            "Our carbon offset certificates are filed in our central archives and prove full carbon neutrality.",
            [passage],
        )
        assert verdict.verdict == VERDICT_INSUFFICIENT

    def test_internal_approval_cannot_override_universal_safety_rules(self, engine):
        passage = _make_passage(
            "5. HEALTH, SAFETY, AND ENVIRONMENTAL CLAIMS Materials must not claim a product cures or treats a disease."
        )
        verdict = engine.classify(
            "test-univ-1",
            "Compliance has signed off on describing our new sedan as 100% safe for all driving conditions.",
            [passage],
        )
        # Absolute safety claims are universally prohibited regardless of purported internal signoff
        assert verdict.verdict == VERDICT_CONTRADICTED


class TestTask4PolicyNuanceAndCompoundClaims:
    """Verifies compound claims with embedded violations and approximate vs exact percentage handling."""

    def test_compound_claim_containing_violation_contradicted(self, engine):
        passage = _make_passage(
            "1. BRAND LOGO The BrandSentry emblem must always appear with at least 20px clear space. "
            "6. SECURITY CLAIMS Do not state that customer data is completely secure or impossible to hack."
        )
        verdict = engine.classify(
            "test-compound-1",
            "Our emblem maintains a 20px clear margin, and our platform guarantees 100% security against all hackers.",
            [passage],
        )
        # Part is compliant, but the second clause is an absolute security guarantee -> CONTRADICTED
        assert verdict.verdict == VERDICT_CONTRADICTED

    def test_approximate_percentage_without_documentation_contradicted(self, engine):
        passage = _make_passage(
            "4. PERFORMANCE CLAIMS Claims about performance must be supported by current, reproducible evidence. "
            "Do not state a specific percentage improvement unless the underlying measurement and methodology are documented."
        )
        verdict = engine.classify(
            "test-apx-1",
            "Users achieve roughly 35% faster document turnaround times.",
            [passage],
        )
        assert verdict.verdict == VERDICT_CONTRADICTED

