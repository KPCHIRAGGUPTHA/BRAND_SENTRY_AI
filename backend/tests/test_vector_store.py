"""
Unit and Integration Tests for ChromaDB Vector Store Service
"""
import pytest
from backend.app.services.chunking import GuidelineChunk
from backend.app.retrieval.vector_store import VectorStoreService


def test_vector_store_add_and_search(tmp_path):
    """Verify adding chunks and querying with filtering in ChromaDB."""
    persist_dir = str(tmp_path / "chroma_test")
    vs = VectorStoreService(persist_dir=persist_dir, collection_name="test_collection")

    chunks = [
        GuidelineChunk(
            chunk_id="doc1_c0",
            document_id="doc-1",
            source_filename="guidelines.pdf",
            page_number=1,
            chunk_index=0,
            text="Brand logo must always be positioned at top right with 20px padding.",
            word_count=12,
            char_count=71,
        ),
        GuidelineChunk(
            chunk_id="doc1_c1",
            document_id="doc-1",
            source_filename="guidelines.pdf",
            page_number=2,
            chunk_index=1,
            text="Comparative claims against competitors require third-party lab verification.",
            word_count=9,
            char_count=76,
        ),
        GuidelineChunk(
            chunk_id="doc2_c0",
            document_id="doc-2",
            source_filename="partner_rules.txt",
            page_number=1,
            chunk_index=0,
            text="Partner co-branding requires written legal approval.",
            word_count=7,
            char_count=52,
        ),
    ]

    # Deterministic dummy embeddings of dimension 4
    embeddings = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]

    added = vs.add_chunks(chunks, embeddings)
    assert added == 3
    assert vs.count() == 3

    # Query matching chunk 1
    query_vec = [0.0, 0.95, 0.0, 0.0]
    matches = vs.search(query_vec, top_k=2)
    assert len(matches) == 2
    # Top match should be doc1_c1
    assert matches[0]["chunk_id"] == "doc1_c1"
    assert "Comparative claims" in matches[0]["text"]
    assert matches[0]["document_id"] == "doc-1"
    assert matches[0]["page_number"] == 2
    assert "distance" in matches[0]
    assert "similarity_score" in matches[0]


def test_vector_store_document_filtering(tmp_path):
    """Verify filtering retrieval by document_id excludes other documents."""
    persist_dir = str(tmp_path / "chroma_filter_test")
    vs = VectorStoreService(persist_dir=persist_dir, collection_name="test_filter")

    chunks = [
        GuidelineChunk(
            chunk_id="d1_c0",
            document_id="doc-A",
            source_filename="a.txt",
            page_number=1,
            chunk_index=0,
            text="Document A policy clause.",
            word_count=4,
            char_count=25,
        ),
        GuidelineChunk(
            chunk_id="d2_c0",
            document_id="doc-B",
            source_filename="b.txt",
            page_number=1,
            chunk_index=0,
            text="Document B policy clause.",
            word_count=4,
            char_count=25,
        ),
    ]
    embeddings = [
        [0.5, 0.5, 0.0, 0.0],
        [0.5, 0.5, 0.0, 0.0],
    ]
    vs.add_chunks(chunks, embeddings)

    # Filter by doc-B only
    results = vs.search([0.5, 0.5, 0.0, 0.0], document_id="doc-B", top_k=5)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "d2_c0"
    assert results[0]["document_id"] == "doc-B"


def test_vector_store_idempotent_upsert(tmp_path):
    """Verify that re-indexing identical chunks does not duplicate records."""
    persist_dir = str(tmp_path / "chroma_idempotent")
    vs = VectorStoreService(persist_dir=persist_dir, collection_name="test_idem")

    chunk = GuidelineChunk(
        chunk_id="doc_idem_c0",
        document_id="doc-idem",
        source_filename="idem.txt",
        page_number=1,
        chunk_index=0,
        text="Unique clause text.",
        word_count=3,
        char_count=19,
    )
    vs.add_chunks([chunk], [[1.0, 0.0, 0.0, 0.0]])
    assert vs.count() == 1

    # Re-insert the same chunk
    vs.add_chunks([chunk], [[1.0, 0.0, 0.0, 0.0]])
    assert vs.count() == 1


def test_vector_store_persistence_reload(tmp_path):
    """Verify that persistent storage can be closed and reopened with data intact."""
    persist_dir = str(tmp_path / "chroma_persist_reload")

    # Instance 1
    vs1 = VectorStoreService(persist_dir=persist_dir, collection_name="reload_test")
    chunk = GuidelineChunk(
        chunk_id="reload_c0",
        document_id="doc-reload",
        source_filename="reload.txt",
        page_number=1,
        chunk_index=0,
        text="Persistent clause that survives restart.",
        word_count=5,
        char_count=40,
    )
    vs1.add_chunks([chunk], [[0.0, 1.0, 0.0, 0.0]])
    assert vs1.count() == 1

    # Instance 2 targeting identical persist_dir
    vs2 = VectorStoreService(persist_dir=persist_dir, collection_name="reload_test")
    assert vs2.count() == 1

    matches = vs2.search([0.0, 1.0, 0.0, 0.0], top_k=1)
    assert len(matches) == 1
    assert matches[0]["chunk_id"] == "reload_c0"
    assert "survives restart" in matches[0]["text"]
