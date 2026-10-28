"""
Unit and Integration Tests for Hybrid Retrieval (BM25 + Dense + RRF)
Covers BM25RetrieverService, HybridRetrieverService, and RRF rank fusion.
"""
import pytest
from backend.app.services.chunking import GuidelineChunk
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService


@pytest.fixture
def temp_bm25(tmp_path):
    """Provides a fresh isolated BM25RetrieverService."""
    persist_dir = str(tmp_path / "bm25")
    return BM25RetrieverService(persist_dir=persist_dir)


@pytest.fixture
def sample_chunks():
    """Sample guideline chunks covering exact keywords, numbers, and policies."""
    def make_chunk(cid, doc_id, fname, page, idx, text):
        return GuidelineChunk(
            chunk_id=cid,
            document_id=doc_id,
            source_filename=fname,
            page_number=page,
            chunk_index=idx,
            text=text,
            word_count=len(text.split()),
            char_count=len(text),
        )

    return [
        make_chunk(
            "doc1-chunk-1",
            "doc1",
            "guidelines_brand.pdf",
            1,
            0,
            "Brand logo must always be positioned in the top-left corner with at least 20px clear margin.",
        ),
        make_chunk(
            "doc1-chunk-2",
            "doc1",
            "guidelines_brand.pdf",
            2,
            1,
            "Any claim containing 100% guaranteed or clinically proven is strictly prohibited in marketing copy.",
        ),
        make_chunk(
            "doc2-chunk-1",
            "doc2",
            "healthcare_policy.txt",
            1,
            0,
            "Medical devices must state FDA approved or CE marked with specific registration number 9845-A.",
        ),
        make_chunk(
            "doc2-chunk-2",
            "doc2",
            "healthcare_policy.txt",
            2,
            1,
            "Pricing discount claims cannot exceed 50% without prior compliance officer authorization.",
        ),
    ]


class TestBM25Retriever:
    def test_empty_query_returns_empty_list(self, temp_bm25):
        assert temp_bm25.search("") == []
        assert temp_bm25.search("   ") == []

    def test_empty_index_returns_empty_list(self, temp_bm25):
        assert temp_bm25.search("logo placement") == []

    def test_add_chunks_and_exact_keyword_match(self, temp_bm25, sample_chunks):
        count = temp_bm25.add_chunks(sample_chunks)
        assert count == 4
        assert temp_bm25.count() == 4

        # Search for exact technical term
        results = temp_bm25.search("20px margin logo", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc1-chunk-1"
        assert "20px" in results[0]["text"]
        assert results[0]["bm25_score"] > 0

    def test_numerical_threshold_search(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)
        results = temp_bm25.search("registration number 9845-A", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc2-chunk-1"

    def test_document_scoping_enforced(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)
        # Search query matching doc2 but scope to doc1
        results = temp_bm25.search("registration number 9845-A", document_id="doc1")
        assert len(results) == 0

        # Scope to doc2
        results_doc2 = temp_bm25.search("registration number 9845-A", document_id="doc2")
        assert len(results_doc2) == 1
        assert results_doc2[0]["document_id"] == "doc2"

    def test_delete_document_removes_chunks(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)
        deleted = temp_bm25.delete_document("doc1")
        assert deleted == 2
        assert temp_bm25.count() == 2

        results = temp_bm25.search("logo corner")
        assert len(results) == 0

    def test_persistence_across_service_reinstantiation(self, tmp_path, sample_chunks):
        persist_dir = str(tmp_path / "persist_test")
        svc1 = BM25RetrieverService(persist_dir=persist_dir)
        svc1.add_chunks(sample_chunks)
        assert svc1.count() == 4

        # Reinstantiate new service targeting same path
        svc2 = BM25RetrieverService(persist_dir=persist_dir)
        assert svc2.count() == 4
        results = svc2.search("top-left corner")
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc1-chunk-1"


class TestHybridRetrieverRRF:
    def test_rrf_scoring_and_deduplication(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        # Mock vector store
        class MockVectorStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                # Return doc1-chunk-2 as nearest dense match
                return [
                    {
                        "chunk_id": "doc1-chunk-2",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 2,
                        "chunk_index": 1,
                        "text": "Any claim containing 100% guaranteed or clinically proven is strictly prohibited in marketing copy.",
                        "distance": 0.15,
                        "similarity_score": 0.85,
                    }
                ]

        class MockEmbeddingService:
            def generate_query_embedding(self, query):
                return [0.1] * 384

        hybrid_svc = HybridRetrieverService(
            vector_store=MockVectorStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
            smoothing_k=60,
        )

        # Query matches doc1-chunk-2 in both dense and lexical
        results = hybrid_svc.search("100% guaranteed clinically proven", mode="hybrid", top_k=3)
        assert len(results) > 0
        top_match = results[0]
        assert top_match["chunk_id"] == "doc1-chunk-2"
        assert "rrf_score" in top_match
        assert top_match["rrf_score"] > 0
        # RRF score should be approx (1/(60+1) + 1/(60+1)) = 2/61 ≈ 0.03278
        expected_rrf = round(1.0 / 61.0 + 1.0 / 61.0, 6)
        assert abs(top_match["rrf_score"] - expected_rrf) < 0.005

    def test_retrieval_modes(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class MockVectorStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [{
                    "chunk_id": "dense-only-1",
                    "document_id": "doc1",
                    "source_filename": "f.pdf",
                    "page_number": 1,
                    "chunk_index": 0,
                    "text": "Dense vector semantic passage",
                    "distance": 0.1,
                    "similarity_score": 0.9,
                }]

        class MockEmbeddingService:
            def generate_query_embedding(self, query):
                return [0.0] * 384

        hybrid_svc = HybridRetrieverService(
            vector_store=MockVectorStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )

        dense_res = hybrid_svc.search("query", mode="dense", top_k=1)
        assert len(dense_res) == 1
        assert dense_res[0]["chunk_id"] == "dense-only-1"

        bm25_res = hybrid_svc.search("registration number 9845-A", mode="bm25", top_k=1)
        assert len(bm25_res) == 1
        assert bm25_res[0]["chunk_id"] == "doc2-chunk-1"
