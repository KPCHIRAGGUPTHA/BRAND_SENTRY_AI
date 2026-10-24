"""
Extended Embedding Service Tests — Model Identity and Consistency

Supplements test_embeddings.py with tests that verify:
1. The active engine is the expected all-MiniLM-L6-v2 model.
2. Model name mis-configuration raises an actionable error at init time.
3. Document and query embeddings are produced by the same model instance
   and therefore interoperable (dot products are meaningful).
4. Embeddings are consistent: same input → same output.
"""
import pytest
import numpy as np
from backend.app.retrieval.embeddings import (
    EmbeddingService,
    _SUPPORTED_MODEL_NAME,
    _EXPECTED_DIMENSION,
)


class TestEmbeddingModelIdentity:
    """Verify that model selection is explicit and consistent."""

    def test_active_model_name_matches_supported(self):
        """The service model_name must equal the declared supported model."""
        svc = EmbeddingService()
        assert svc.model_name == _SUPPORTED_MODEL_NAME, (
            f"model_name is '{svc.model_name}', expected '{_SUPPORTED_MODEL_NAME}'"
        )

    def test_unsupported_model_raises_at_init(self):
        """Constructing the service with a different model name must raise RuntimeError."""
        with pytest.raises(RuntimeError, match="does not match the only supported model"):
            EmbeddingService(model_name="paraphrase-MiniLM-L6-v2")

    def test_active_engine_reported_after_first_call(self):
        """active_engine should be a non-empty, non-'uninitialised' string after first use."""
        svc = EmbeddingService()
        svc.generate_query_embedding("warm-up")
        assert svc.active_engine != "uninitialised"
        assert len(svc.active_engine) > 0

    def test_expected_dimension_constant_is_384(self):
        """Sanity: the declared expected dimension must be 384."""
        assert _EXPECTED_DIMENSION == 384

    def test_dimension_property_matches_expected(self):
        """dimension property must match the declared constant after lazy init."""
        svc = EmbeddingService()
        svc.generate_query_embedding("trigger init")
        assert svc.dimension == _EXPECTED_DIMENSION


class TestDocumentQueryEmbeddingInteroperability:
    """
    Verify that document and query embeddings are produced by the same model
    so that their dot products are semantically meaningful.
    """

    def test_same_text_via_both_methods_returns_same_vector(self):
        """
        generate_embeddings([text]) and generate_query_embedding(text) must return
        the same vector.  If they used different models the vectors would differ.
        """
        svc = EmbeddingService()
        text = "The corporate logo must maintain a clear zone of 20px around it."
        via_batch = svc.generate_embeddings([text])[0]
        via_query = svc.generate_query_embedding(text)
        np.testing.assert_allclose(
            via_batch,
            via_query,
            rtol=1e-5,
            atol=1e-5,
            err_msg="generate_embeddings and generate_query_embedding returned different vectors",
        )

    def test_related_texts_more_similar_than_unrelated(self):
        """
        Semantically related texts should have higher cosine similarity than
        unrelated texts when using the same model for both query and docs.
        This test would fail if document vs query embeddings came from different models.
        """
        svc = EmbeddingService()
        query = "logo placement requirements"
        related = "The brand logo must always appear in the top-right corner with padding."
        unrelated = "Financial reporting standards require quarterly disclosures."

        q_emb = np.array(svc.generate_query_embedding(query))
        r_emb = np.array(svc.generate_embeddings([related])[0])
        u_emb = np.array(svc.generate_embeddings([unrelated])[0])

        sim_related = float(np.dot(q_emb, r_emb))   # unit vectors → dot = cosine sim
        sim_unrelated = float(np.dot(q_emb, u_emb))

        assert sim_related > sim_unrelated, (
            f"Expected related text to be more similar to query "
            f"(sim_related={sim_related:.4f} vs sim_unrelated={sim_unrelated:.4f})"
        )
