"""
Unit and Integration Tests for Stage 2 Hybrid Retrieval and Reranking Architecture.
Covers all 16 required test scenarios:
1. Dense retrieval.
2. BM25 exact phrase retrieval.
3. BM25 numerical retrieval.
4. Negation-sensitive retrieval.
5. Hybrid result fusion (RRF).
6. Duplicate chunk removal.
7. Missing BM25 results fallback.
8. Missing dense results fallback.
9. Empty retrieval handling.
10. Document scope isolation.
11. Metadata preservation (rerank_score, rrf_score, bm25_score, page numbers).
12. Conflicting evidence preservation.
13. Reranker ordering (cross-encoder elevates exact match).
14. Reranker failure fallback (when model loading fails, returns RRF order).
15. Cross-encoder model loading behavior (singleton thread-safe loading).
16. Stage 1 verdict behavior after retrieval integration (unsupported efficacy language rejected).
"""
import pytest
from unittest.mock import MagicMock, patch
from backend.app.services.chunking import GuidelineChunk
from backend.app.retrieval.bm25_retriever import BM25RetrieverService
from backend.app.retrieval.hybrid_retriever import HybridRetrieverService
from backend.app.retrieval.reranker import CrossEncoderRerankerService
from backend.app.services.verdict_engine import verdict_engine


@pytest.fixture
def temp_bm25(tmp_path):
    """Provides a fresh isolated BM25RetrieverService."""
    persist_dir = str(tmp_path / "bm25")
    return BM25RetrieverService(persist_dir=persist_dir)


@pytest.fixture
def sample_chunks():
    """Sample guideline chunks covering exact keywords, numbers, policies, and conflicting claims."""
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
        make_chunk(
            "doc1-chunk-conflict-a",
            "doc1",
            "guidelines_brand.pdf",
            3,
            2,
            "Customer testimonials require written legal approval prior to external publication.",
        ),
        make_chunk(
            "doc1-chunk-conflict-b",
            "doc1",
            "guidelines_brand.pdf",
            4,
            3,
            "Customer testimonials from verified buyers do not require legal approval if anonymized.",
        ),
    ]


class MockEmbeddingService:
    def generate_query_embedding(self, query):
        return [0.1] * 384

    def generate_embeddings(self, texts):
        return [[0.1] * 384 for _ in texts]


# =========================================================================
# Phase H: 16 Regression Test Scenarios
# =========================================================================

class TestHybridRetrievalRegressionSuite:

    # 1. Dense retrieval
    def test_1_dense_retrieval(self, temp_bm25, sample_chunks):
        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc1-chunk-1",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "text": sample_chunks[0].text,
                        "distance": 0.12,
                        "similarity_score": 0.88,
                    }
                ]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )
        results = retriever.search("visual identity layout", mode="dense", top_k=2)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "doc1-chunk-1"
        assert results[0]["similarity_score"] == 0.88
        assert "distance" in results[0]

    # 2. BM25 exact phrase retrieval
    def test_2_bm25_exact_phrase_retrieval(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)
        results = temp_bm25.search("Brand logo must always be positioned", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc1-chunk-1"
        assert results[0]["bm25_score"] > 0

    # 3. BM25 numerical retrieval
    def test_3_bm25_numerical_retrieval(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)
        results = temp_bm25.search("at least 20px clear margin", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc1-chunk-1"
        assert "20px" in results[0]["text"]

    # 4. Negation-sensitive retrieval
    def test_4_negation_sensitive_retrieval(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)
        results = temp_bm25.search("strictly prohibited marketing copy 100% guaranteed", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc1-chunk-2"
        assert "strictly prohibited" in results[0]["text"]

    # 5. Hybrid result fusion (RRF)
    def test_5_hybrid_result_fusion_rrf(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc1-chunk-2",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 2,
                        "chunk_index": 1,
                        "text": sample_chunks[1].text,
                        "distance": 0.10,
                        "similarity_score": 0.90,
                    }
                ]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
            smoothing_k=60,
        )
        results = retriever.search("100% guaranteed clinically proven", mode="hybrid", top_k=3)
        assert len(results) > 0
        top_match = results[0]
        assert top_match["chunk_id"] == "doc1-chunk-2"
        assert "rrf_score" in top_match
        # RRF formula check: item ranked #1 in dense and #1 in BM25: 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.032787
        expected_score = round(1.0 / 61.0 + 1.0 / 61.0, 6)
        assert abs(top_match["rrf_score"] - expected_score) < 0.005

    # 6. Duplicate chunk removal
    def test_6_duplicate_chunk_removal(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                # Returns the same chunk twice or chunk that BM25 also returns
                return [
                    {
                        "chunk_id": "doc1-chunk-1",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "text": sample_chunks[0].text,
                        "distance": 0.15,
                        "similarity_score": 0.85,
                    },
                    {
                        "chunk_id": "doc1-chunk-1",  # duplicate
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "text": sample_chunks[0].text,
                        "distance": 0.15,
                        "similarity_score": 0.85,
                    },
                ]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )
        results = retriever.search("logo margin corner", mode="hybrid", top_k=5)
        chunk_ids = [r["chunk_id"] for r in results]
        assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk IDs must be deduplicated"

    # 7. Missing BM25 results fallback
    def test_7_missing_bm25_results_fallback(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc2-chunk-2",
                        "document_id": "doc2",
                        "source_filename": "healthcare_policy.txt",
                        "page_number": 2,
                        "chunk_index": 1,
                        "text": sample_chunks[3].text,
                        "distance": 0.20,
                        "similarity_score": 0.80,
                    }
                ]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )
        # Query containing out-of-vocabulary words that BM25 cannot match
        results = retriever.search("unprecedented promotional concessions and rebates", mode="hybrid", top_k=3)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc2-chunk-2"

    # 8. Missing dense results fallback
    def test_8_missing_dense_results_fallback(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class EmptyDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return []

        retriever = HybridRetrieverService(
            vector_store=EmptyDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )
        # Query that BM25 can match even when dense yields nothing
        results = retriever.search("registration number 9845-A", mode="hybrid", top_k=3)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc2-chunk-1"

    # 9. Empty retrieval handling
    def test_9_empty_retrieval_handling(self, temp_bm25):
        class EmptyDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return []

        retriever = HybridRetrieverService(
            vector_store=EmptyDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )
        # Test empty query string
        assert retriever.search("", mode="hybrid") == []
        assert retriever.search("   ", mode="hybrid") == []
        # Test query with zero matches across both engines
        assert retriever.search("completely non-existent terms xyz987", mode="hybrid") == []

    # 10. Document scope isolation
    def test_10_document_scope_isolation(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class ScopedDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                # Only return items belonging to scoped document_id
                items = [
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "source_filename": c.source_filename,
                        "page_number": c.page_number,
                        "chunk_index": c.chunk_index,
                        "text": c.text,
                        "distance": 0.2,
                        "similarity_score": 0.8,
                    }
                    for c in sample_chunks
                    if document_id is None or c.document_id == document_id
                ]
                return items[:top_k]

        retriever = HybridRetrieverService(
            vector_store=ScopedDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )

        # Query matching doc2 content, but strictly scoped to doc1
        results = retriever.search("registration number 9845-A", document_id="doc1", mode="hybrid")
        for r in results:
            assert r["document_id"] == "doc1", "Passages from other documents must never leak through scope"

    # 11. Metadata preservation (rerank_score, rrf_score, bm25_score, page numbers)
    def test_11_metadata_preservation(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc1-chunk-1",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 42,
                        "chunk_index": 7,
                        "text": sample_chunks[0].text,
                        "distance": 0.15,
                        "similarity_score": 0.85,
                    }
                ]

        class MockReranker:
            def rerank(self, query, candidates, top_k=5):
                for c in candidates:
                    c["rerank_score"] = 4.25
                return candidates[:top_k]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
            reranker=MockReranker(),
        )
        results = retriever.search("logo placement corner margin", mode="hybrid_rerank", top_k=1)
        assert len(results) == 1
        item = results[0]
        assert item["chunk_id"] == "doc1-chunk-1"
        assert item["document_id"] == "doc1"
        assert item["source_filename"] == "guidelines_brand.pdf"
        assert item["page_number"] == 42
        assert item["chunk_index"] == 7
        assert "rrf_score" in item
        assert "similarity_score" in item
        assert item.get("rerank_score") == 4.25

    # 12. Conflicting evidence preservation
    def test_12_conflicting_evidence_preservation(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class ConflictDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc1-chunk-conflict-a",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 3,
                        "chunk_index": 2,
                        "text": sample_chunks[4].text,
                        "distance": 0.10,
                        "similarity_score": 0.90,
                    },
                    {
                        "chunk_id": "doc1-chunk-conflict-b",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 4,
                        "chunk_index": 3,
                        "text": sample_chunks[5].text,
                        "distance": 0.11,
                        "similarity_score": 0.89,
                    },
                ]

        retriever = HybridRetrieverService(
            vector_store=ConflictDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )
        results = retriever.search("customer testimonials legal approval requirement", mode="hybrid", top_k=5)
        retrieved_cids = {r["chunk_id"] for r in results}
        assert "doc1-chunk-conflict-a" in retrieved_cids
        assert "doc1-chunk-conflict-b" in retrieved_cids, "Both conflicting guideline passages must be preserved"

    # 13. Reranker ordering (cross-encoder elevates exact match)
    def test_13_reranker_ordering(self, temp_bm25):
        reranker = CrossEncoderRerankerService()
        query = "FDA approved medical device registration number 9845-A"
        candidates = [
            {
                "chunk_id": "vague-chunk",
                "text": "General health gadgets should aim for industry standard certifications and safety compliance.",
                "similarity_score": 0.88,
            },
            {
                "chunk_id": "exact-chunk",
                "text": "Medical devices must state FDA approved or CE marked with specific registration number 9845-A.",
                "similarity_score": 0.82,
            },
        ]
        reranked = reranker.rerank(query, candidates, top_k=2)
        assert len(reranked) == 2
        # The exact chunk has definitive token overlap and cross-attention alignment
        assert reranked[0]["chunk_id"] == "exact-chunk"
        assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]

    # 14. Reranker failure fallback (when model loading fails, returns RRF order)
    def test_14_reranker_failure_fallback(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class BrokenReranker(CrossEncoderRerankerService):
            def rerank(self, query, candidates, top_k=5):
                raise RuntimeError("ONNX runtime execution memory failure simulation")

        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc1-chunk-1",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "text": sample_chunks[0].text,
                        "distance": 0.15,
                        "similarity_score": 0.85,
                    }
                ]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
            reranker=BrokenReranker(),
        )
        # Should gracefully log error and return RRF order without raising RuntimeError
        results = retriever.search("logo margin", mode="hybrid_rerank", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "doc1-chunk-1"

    # 15. Cross-encoder model loading behavior (singleton thread-safe loading)
    def test_15_cross_encoder_singleton_loading(self):
        svc = CrossEncoderRerankerService()
        # Initial ensure_loaded call
        assert svc.ensure_loaded() is True
        session1 = svc._session
        tokenizer1 = svc._tokenizer

        # Second call returns existing session without re-instantiation
        assert svc.ensure_loaded() is True
        assert svc._session is session1
        assert svc._tokenizer is tokenizer1

    # 16. Stage 1 verdict behavior after retrieval integration (unsupported efficacy language rejected)
    def test_16_stage1_verdict_behavior_after_retrieval(self, temp_bm25, sample_chunks):
        temp_bm25.add_chunks(sample_chunks)

        class MockDenseStore:
            def search(self, query_embedding, document_id=None, top_k=5):
                return [
                    {
                        "chunk_id": "doc1-chunk-2",
                        "document_id": "doc1",
                        "source_filename": "guidelines_brand.pdf",
                        "page_number": 2,
                        "chunk_index": 1,
                        "text": sample_chunks[1].text,
                        "distance": 0.12,
                        "similarity_score": 0.88,
                    }
                ]

        retriever = HybridRetrieverService(
            vector_store=MockDenseStore(),
            bm25_service=temp_bm25,
            embeddings=MockEmbeddingService(),
        )

        # Claim with unsupported efficacy/guarantee language
        query = "Our supplement is 100% guaranteed to cure insomnia."
        passages = retriever.search(query, mode="hybrid_rerank", top_k=3)
        assert len(passages) > 0

        # Run verdict engine
        verdict = verdict_engine.classify(
            claim_id="claim-efficacy-check",
            claim_text=query,
            retrieved_passages=passages,
        )

        # Must NOT be SUPPORTED
        assert verdict.verdict != "SUPPORTED"
        assert verdict.compliance_verdict != "SUPPORTED"
        # Must NOT provide an unsafe efficacy rewrite as a suggested correction
        if verdict.suggested_correction:
            assert "100% guaranteed" not in verdict.suggested_correction.lower()
            assert "cure" not in verdict.suggested_correction.lower()
