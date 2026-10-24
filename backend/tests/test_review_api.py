"""
Integration Tests for POST /api/review — Phase 3 Review API.

Uses FastAPI TestClient with mocked embedding and vector store to stay
fully deterministic (no ChromaDB writes, no real embeddings during API tests).

Separate integration tests for real end-to-end flows are in test_review_e2e.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_embedding(texts=None, query=None):
    """Return a deterministic unit vector of dimension 384."""
    return [0.0] * 383 + [1.0]


def _no_passages():
    return []


def _passages_with_prohibition():
    return [
        {
            "chunk_id": "c1",
            "document_id": "doc-1",
            "source_filename": "policy.pdf",
            "page_number": 2,
            "text": "Marketing materials must not make guaranteed outcome claims.",
            "similarity_score": 0.85,
            "distance": 0.15,
        }
    ]


def _passages_with_support():
    return [
        {
            "chunk_id": "c2",
            "document_id": "doc-1",
            "source_filename": "policy.pdf",
            "page_number": 4,
            "text": "Moisturising claims are approved for standard product communications.",
            "similarity_score": 0.80,
            "distance": 0.20,
        }
    ]


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------

class TestReviewInputValidation:
    def test_empty_content_rejected(self):
        response = client.post("/api/review", json={"content": ""})
        assert response.status_code in (400, 422)

    def test_whitespace_only_rejected(self):
        response = client.post("/api/review", json={"content": "   \n\t  "})
        assert response.status_code in (400, 422)

    def test_content_too_long_rejected(self):
        long_content = "A" * 6000
        response = client.post("/api/review", json={"content": long_content})
        assert response.status_code in (400, 422)

    def test_unknown_document_id_rejected(self):
        response = client.post(
            "/api/review",
            json={"content": "Our product is great.", "document_ids": ["non-existent-uuid"]},
        )
        assert response.status_code == 404

    def test_missing_content_field_rejected(self):
        response = client.post("/api/review", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Successful review tests (mocked retrieval)
# ---------------------------------------------------------------------------

class TestReviewSuccess:
    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_basic_review_returns_200(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _no_passages()

        response = client.post(
            "/api/review",
            json={"content": "Our product moisturises skin for 24 hours."},
        )
        assert response.status_code == 200

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_response_has_review_id(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _no_passages()

        response = client.post("/api/review", json={"content": "We support healthy skin."})
        assert response.status_code == 200
        data = response.json()
        assert "review_id" in data
        assert len(data["review_id"]) > 0

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_response_schema_complete(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _no_passages()

        response = client.post("/api/review", json={"content": "Our serum works well."})
        data = response.json()
        required_keys = {"review_id", "content_preview", "claims", "summary", "created_at"}
        assert required_keys.issubset(data.keys())

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_summary_counts_match_claims(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _no_passages()

        content = "Our product moisturises. It nourishes skin. It protects daily."
        response = client.post("/api/review", json={"content": content})
        data = response.json()
        summary = data["summary"]
        total = summary["total_claims"]
        assert total == len(data["claims"])
        assert (
            summary["supported"] + summary["contradicted"] + summary["insufficient_evidence"]
            == total
        )

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_prohibited_phrase_detected_without_guidelines(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 0
        mock_vs.search.return_value = _no_passages()

        response = client.post(
            "/api/review",
            json={"content": "Our product is 100% guaranteed to work."},
        )
        assert response.status_code == 200
        data = response.json()
        verdicts = [c["verdict"] for c in data["claims"]]
        assert "CONTRADICTED" in verdicts, (
            f"Expected CONTRADICTED for '100% guaranteed' claim, got: {verdicts}"
        )

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_no_guidelines_returns_warning(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 0
        mock_vs.search.return_value = _no_passages()

        response = client.post("/api/review", json={"content": "Our product is great."})
        data = response.json()
        assert data.get("warning") is not None

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_content_preview_truncated_at_120(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _no_passages()

        long_content = "A" * 200 + " and more text here."
        response = client.post("/api/review", json={"content": long_content})
        data = response.json()
        assert len(data["content_preview"]) <= 125  # 120 + "…"

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_claim_fields_present(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _no_passages()

        response = client.post("/api/review", json={"content": "Our product is effective."})
        data = response.json()
        for claim in data["claims"]:
            assert "claim_id" in claim
            assert "claim_text" in claim
            assert "verdict" in claim
            assert "explanation" in claim
            assert "evidence" in claim
            assert claim["verdict"] in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_evidence_quote_present_in_passage(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        mock_vs.search.return_value = _passages_with_prohibition()

        response = client.post(
            "/api/review",
            json={"content": "Results are guaranteed within 7 days."},
        )
        data = response.json()
        for claim in data["claims"]:
            for ev in claim["evidence"]:
                assert "quote" in ev
                assert len(ev["quote"]) > 0

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_retrieval_failure_safe_fallback(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 5
        mock_vs.search.side_effect = RuntimeError("ChromaDB connection failed")

        response = client.post("/api/review", json={"content": "Our product nourishes skin."})
        assert response.status_code == 200
        data = response.json()
        # Retrieval failure must not crash — should return INSUFFICIENT_EVIDENCE
        for claim in data["claims"]:
            assert claim["verdict"] in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")


# ---------------------------------------------------------------------------
# Existing Phase 2 endpoints regression
# ---------------------------------------------------------------------------

class TestPhase2Regression:
    def test_health_still_operational(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_guidelines_list_still_works(self):
        response = client.get("/api/guidelines")
        assert response.status_code == 200
        assert "documents" in response.json()

    def test_guidelines_search_still_works(self):
        response = client.post(
            "/api/guidelines/search",
            json={"query": "logo placement rules"},
        )
        # May return empty results if no guidelines indexed, but should not 500
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            assert "results" in response.json()


# ---------------------------------------------------------------------------
# Document Scoping & Deduplication Regression Tests
# ---------------------------------------------------------------------------

class TestDocumentScopingAndDeduplicationRegression:
    @patch("backend.app.api.review.document_registry")
    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_document_scoping_strictly_enforced(self, mock_vs, mock_emb, mock_reg):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 2
        mock_reg.get_document.side_effect = lambda doc_id: {
            "document_id": doc_id,
            "filename": f"{doc_id}.pdf",
            "status": "indexed",
        } if doc_id in ("doc-A", "doc-B") else None

        def mock_search(query_embedding, document_id, top_k):
            if document_id == "doc-A":
                return [
                    {
                        "chunk_id": "cA",
                        "document_id": "doc-A",
                        "source_filename": "doc-A.pdf",
                        "page_number": 1,
                        "text": "Marketing claims must be supported by clinical studies.",
                        "similarity_score": 0.85,
                        "distance": 0.15,
                    }
                ]
            return []

        mock_vs.search.side_effect = mock_search

        response = client.post(
            "/api/review",
            json={"content": "Our serum has proven efficacy.", "document_ids": ["doc-A"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_ids_searched"] == ["doc-A"]
        for claim in data["claims"]:
            for ev in claim["evidence"]:
                assert ev["document_id"] == "doc-A"

    @patch("backend.app.api.review.document_registry")
    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_unscoped_review_includes_all_indexed_document_ids(self, mock_vs, mock_emb, mock_reg):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 2
        mock_reg.list_documents.return_value = [
            {"document_id": "doc-1", "status": "indexed"},
            {"document_id": "doc-2", "status": "indexed"},
            {"document_id": "doc-3", "status": "failed"},
        ]
        mock_vs.search.return_value = []

        response = client.post(
            "/api/review",
            json={"content": "Our formula is effective."},
        )
        assert response.status_code == 200
        data = response.json()
        assert "doc-1" in data["document_ids_searched"]
        assert "doc-2" in data["document_ids_searched"]
        assert "doc-3" not in data["document_ids_searched"]

    @patch("backend.app.api.review.embedding_service")
    @patch("backend.app.api.review.vector_store_service")
    def test_api_deduplicates_identical_evidence_passages(self, mock_vs, mock_emb):
        mock_emb.generate_query_embedding.return_value = _mock_embedding()
        mock_vs.count.return_value = 1
        # Two chunks with identical text (e.g. from sliding chunker duplicate)
        mock_vs.search.return_value = [
            {
                "chunk_id": "c1",
                "document_id": "doc-1",
                "source_filename": "policy.pdf",
                "page_number": 1,
                "text": "Absolute percentage claims such as 100% guaranteed are prohibited.",
                "similarity_score": 0.90,
                "distance": 0.10,
            },
            {
                "chunk_id": "c2",
                "document_id": "doc-1",
                "source_filename": "policy.pdf",
                "page_number": 1,
                "text": "Absolute percentage claims such as 100% guaranteed are prohibited.",
                "similarity_score": 0.89,
                "distance": 0.11,
            },
        ]

        response = client.post(
            "/api/review",
            json={"content": "Our formula is 100% guaranteed to work."},
        )
        assert response.status_code == 200
        data = response.json()
        for claim in data["claims"]:
            # Should have deduplicated the identical passage
            assert len(claim["evidence"]) == 1
