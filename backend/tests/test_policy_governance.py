"""
Unit and Integration Tests for Policy Governance & Auditable Reviews (Improvement 2).
Covers policy versioning, audit trail persistence, dashboard analytics, and JSON/CSV/PDF exports.
"""
import json
import pytest
from backend.app.services.document_registry import DocumentRegistry
from backend.app.services.audit_service import AuditService


@pytest.fixture
def temp_registry(tmp_path):
    db_path = str(tmp_path / "test_docs.db")
    return DocumentRegistry(db_path=db_path)


@pytest.fixture
def temp_audit(tmp_path):
    db_path = str(tmp_path / "test_reviews.db")
    return AuditService(db_path=db_path)


class TestPolicyVersioning:
    def test_register_and_list_policy_versions(self, temp_registry):
        # Register document
        temp_registry.register_document(
            document_id="doc-1",
            filename="brand_guide_v1.pdf",
            file_type="pdf",
            file_size=1024,
            stored_path="/dummy/path",
            status="indexed",
            content_hash="hash_aaa111",
        )

        # Register policy version
        v1 = temp_registry.register_policy_version(
            document_id="doc-1",
            filename="brand_guide_v1.pdf",
            content_hash="hash_aaa111",
            policy_id="pol-brand-core",
        )

        assert v1["version_label"] == "v1.0"
        assert v1["is_active"] == 1
        assert v1["policy_id"] == "pol-brand-core"

        # Register second version of the same policy
        v2 = temp_registry.register_policy_version(
            document_id="doc-2",
            filename="brand_guide_v2.pdf",
            content_hash="hash_bbb222",
            policy_id="pol-brand-core",
        )

        assert v2["version_label"] == "v2.0"
        assert v2["is_active"] == 1

        # Check v1 was archived
        v1_updated = temp_registry.get_policy_version(v1["version_id"])
        assert v1_updated["is_active"] == 0

        # List all versions
        all_versions = temp_registry.list_policy_versions(policy_id="pol-brand-core")
        assert len(all_versions) == 2

    def test_duplicate_content_reuses_version(self, temp_registry):
        v1 = temp_registry.register_policy_version(
            document_id="doc-1",
            filename="brand_guide.pdf",
            content_hash="hash_identical",
            policy_id="pol-same",
        )

        v2 = temp_registry.register_policy_version(
            document_id="doc-1-dup",
            filename="brand_guide.pdf",
            content_hash="hash_identical",
            policy_id="pol-same",
        )

        assert v1["version_id"] == v2["version_id"]
        assert len(temp_registry.list_policy_versions(policy_id="pol-same")) == 1

    def test_activate_version(self, temp_registry):
        v1 = temp_registry.register_policy_version("doc-1", "g.pdf", "hash_1", "pol-act")
        v2 = temp_registry.register_policy_version("doc-2", "g.pdf", "hash_2", "pol-act")
        assert temp_registry.get_policy_version(v2["version_id"])["is_active"] == 1
        assert temp_registry.get_policy_version(v1["version_id"])["is_active"] == 0

        # Reactivate v1
        success = temp_registry.activate_policy_version(v1["version_id"])
        assert success is True
        assert temp_registry.get_policy_version(v1["version_id"])["is_active"] == 1
        assert temp_registry.get_policy_version(v2["version_id"])["is_active"] == 0


class TestPersistentAuditService:
    def test_save_and_retrieve_review(self, temp_audit):
        claims_sample = [
            {
                "claim_id": "claim-1",
                "claim_text": "We offer 100% guaranteed delivery on all orders.",
                "verdict": "CONTRADICTED",
                "explanation": "Violates absolute guarantee guidelines.",
                "evidence": [
                    {
                        "chunk_id": "chk-1",
                        "document_id": "doc-1",
                        "source_filename": "brand.pdf",
                        "page_number": 1,
                        "quote": "Marketing materials must not use the phrase 100% guaranteed",
                        "similarity_score": 0.88,
                        "distance": 0.12,
                    }
                ],
                "suggested_correction": "We offer reliable, dependable delivery.",
            }
        ]
        summary_sample = {
            "total_claims": 1,
            "supported": 0,
            "contradicted": 1,
            "insufficient_evidence": 0,
        }

        saved = temp_audit.save_review(
            review_id="rev-test-123",
            submitted_content="We offer 100% guaranteed delivery on all orders.",
            claims=claims_sample,
            summary=summary_sample,
            document_ids=["doc-1"],
            review_source="text",
            retrieval_mode="hybrid",
        )

        assert saved["review_id"] == "rev-test-123"
        assert saved["summary"]["contradicted"] == 1
        assert len(saved["claims"]) == 1

        # Retrieve
        fetched = temp_audit.get_review("rev-test-123")
        assert fetched is not None
        assert fetched["review_id"] == "rev-test-123"
        assert fetched["claims"][0]["claim_id"] == "claim-1"

    def test_list_and_dashboard_stats(self, temp_audit):
        temp_audit.save_review(
            review_id="rev-1",
            submitted_content="Content A",
            claims=[],
            summary={"total_claims": 2, "supported": 2, "contradicted": 0, "insufficient_evidence": 0},
            review_source="text",
        )
        temp_audit.save_review(
            review_id="rev-2",
            submitted_content="Content B",
            claims=[],
            summary={"total_claims": 1, "supported": 0, "contradicted": 1, "insufficient_evidence": 0},
            review_source="image",
        )

        listing = temp_audit.list_reviews(limit=10)
        assert listing["total"] == 2
        assert len(listing["reviews"]) == 2

        stats = temp_audit.get_dashboard_stats()
        assert stats["total_reviews"] == 2
        assert stats["total_claims_reviewed"] == 3
        assert stats["total_supported"] == 2
        assert stats["total_contradicted"] == 1
        assert stats["text_reviews_count"] == 1
        assert stats["image_reviews_count"] == 1

    def test_csv_export(self, temp_audit):
        temp_audit.save_review(
            review_id="rev-csv-test",
            submitted_content="Marketing text to export.",
            claims=[{
                "claim_id": "c1",
                "claim_text": "Sample claim",
                "verdict": "SUPPORTED",
                "explanation": "Supported by evidence",
                "evidence": [{"quote": "Guideline quote", "source_filename": "guide.pdf", "page_number": 2}],
                "suggested_correction": None,
            }],
            summary={"total_claims": 1, "supported": 1, "contradicted": 0, "insufficient_evidence": 0},
        )

        csv_str = temp_audit.export_csv("rev-csv-test")
        assert csv_str is not None
        assert "BrandSentry AI — Compliance Review Audit Report" in csv_str
        assert "rev-csv-test" in csv_str
        assert "Sample claim" in csv_str
        assert "SUPPORTED" in csv_str

    def test_pdf_export(self, temp_audit):
        temp_audit.save_review(
            review_id="rev-pdf-test",
            submitted_content="Promotional product launch copy.",
            claims=[{
                "claim_id": "c1",
                "claim_text": "Our product is 100% safe",
                "verdict": "CONTRADICTED",
                "explanation": "Prohibited safety claim",
                "evidence": [{"quote": "Do not describe product as 100% safe", "source_filename": "safety.pdf", "page_number": 1, "similarity_score": 0.91}],
                "suggested_correction": "Product meets tested safety standards.",
            }],
            summary={"total_claims": 1, "supported": 0, "contradicted": 1, "insufficient_evidence": 0},
        )

        pdf_bytes = temp_audit.export_pdf("rev-pdf-test")
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 500
        # Check standard PDF header magic bytes
        assert pdf_bytes.startswith(b"%PDF")


class TestGovernanceAPIEndpoints:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        self.client = TestClient(app)

    def test_list_reviews_endpoint(self):
        resp = self.client.get("/api/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "reviews" in data

    def test_stats_summary_endpoint(self):
        resp = self.client.get("/api/reviews/stats/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_reviews" in data
        assert "total_claims_reviewed" in data
        assert "indexed_guidelines_count" in data

    def test_get_nonexistent_review_returns_404(self):
        resp = self.client.get("/api/reviews/non-existent-uuid-1234")
        assert resp.status_code == 404

    def test_export_endpoints(self):
        from backend.app.services.audit_service import audit_service
        audit_service.save_review(
            review_id="rev-export-endpoint-test",
            submitted_content="100% safe guaranteed outcome.",
            claims=[{
                "claim_id": "c1",
                "claim_text": "100% safe guaranteed outcome.",
                "verdict": "CONTRADICTED",
                "explanation": "Contradicted by policy",
                "evidence": [],
                "suggested_correction": "Safe and dependable",
            }],
            summary={"total_claims": 1, "supported": 0, "contradicted": 1, "insufficient_evidence": 0},
        )

        # JSON
        r_json = self.client.get("/api/reviews/rev-export-endpoint-test/export?format=json")
        assert r_json.status_code == 200
        assert "application/json" in r_json.headers["content-type"]

        # CSV
        r_csv = self.client.get("/api/reviews/rev-export-endpoint-test/export?format=csv")
        assert r_csv.status_code == 200
        assert "text/csv" in r_csv.headers["content-type"]

        # PDF
        r_pdf = self.client.get("/api/reviews/rev-export-endpoint-test/export?format=pdf")
        assert r_pdf.status_code == 200
        assert "application/pdf" in r_pdf.headers["content-type"]
        assert r_pdf.content.startswith(b"%PDF")

    def test_policy_versions_endpoint(self):
        resp = self.client.get("/api/guidelines/versions/list")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
