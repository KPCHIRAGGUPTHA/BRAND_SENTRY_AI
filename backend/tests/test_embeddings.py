"""
Unit Tests for Local Dense Embedding Generation Service
"""
import numpy as np
import pytest
from backend.app.retrieval.embeddings import embedding_service


def test_embedding_dimension_and_type():
    """Verify that generated embeddings have dimension 384 and are list of floats."""
    texts = ["Brand compliance guideline rule number one."]
    embeddings = embedding_service.generate_embeddings(texts)

    assert len(embeddings) == 1
    assert len(embeddings[0]) == 384
    assert isinstance(embeddings[0][0], float)


def test_embedding_finite_and_normalized():
    """Verify that embeddings contain no NaN or Inf, and are normalized unit vectors."""
    texts = [
        "The corporate logo must always have 20px padding.",
        "Comparative claims require independent lab testing.",
    ]
    embeddings = embedding_service.generate_embeddings(texts)
    assert len(embeddings) == 2

    for emb in embeddings:
        arr = np.array(emb, dtype=np.float32)
        assert np.all(np.isfinite(arr)), "Embedding contains non-finite values"
        norm = np.linalg.norm(arr)
        assert pytest.approx(norm, abs=1e-3) == 1.0, f"Embedding is not normalized: norm={norm}"


def test_query_embedding_consistency():
    """Verify query embedding generator returns identical vector for identical input."""
    q = "What is the policy for logo placement?"
    emb1 = embedding_service.generate_query_embedding(q)
    emb2 = embedding_service.generate_query_embedding(q)

    assert len(emb1) == 384
    np.testing.assert_allclose(emb1, emb2, rtol=1e-5, atol=1e-5)


def test_empty_query_raises_error():
    """Verify that empty or whitespace query raises ValueError."""
    with pytest.raises(ValueError):
        embedding_service.generate_query_embedding("")

    with pytest.raises(ValueError):
        embedding_service.generate_query_embedding("   ")
