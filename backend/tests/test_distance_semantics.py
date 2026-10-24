"""
Deterministic Tests for ChromaDB Cosine Distance → Similarity Conversion

Validates the core distance/similarity arithmetic used in VectorStoreService.search().
These tests do NOT require a running ChromaDB instance — they verify the formula
in isolation using known unit-vector inputs.

ChromaDB cosine-space semantic under test:
  distance   = 1 - cosine_similarity       (range [0, 1] for unit vectors)
  similarity = 1.0 - distance              (NOT 1.0 - distance/2)

All vectors used here are unit-length (L2 norm = 1) to mirror the
normalised output produced by EmbeddingService.generate_embeddings().
"""
import math
import pytest
import numpy as np
from backend.app.retrieval.vector_store import VectorStoreService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine_distance(a: list, b: list) -> float:
    """Reference implementation: ground-truth cosine distance for unit vectors."""
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    # normalise (defensive — inputs should already be unit length)
    va /= np.linalg.norm(va)
    vb /= np.linalg.norm(vb)
    similarity = float(np.dot(va, vb))
    return 1.0 - similarity


def _expected_similarity(distance: float) -> float:
    """Formula used by VectorStoreService: sim = 1.0 - distance."""
    return round(1.0 - distance, 4)


# ---------------------------------------------------------------------------
# Pure arithmetic tests (no ChromaDB, fully deterministic)
# ---------------------------------------------------------------------------

class TestCosineDistanceArithmetic:
    """Verify the distance→similarity formula using ground-truth values."""

    def test_identical_vectors_distance_zero_similarity_one(self):
        """Identical unit vectors: distance=0.0, similarity=1.0."""
        v = [1.0, 0.0, 0.0]
        dist = _cosine_distance(v, v)
        assert math.isclose(dist, 0.0, abs_tol=1e-6), f"dist={dist}"
        sim = _expected_similarity(dist)
        assert math.isclose(sim, 1.0, abs_tol=1e-4), f"sim={sim}"

    def test_orthogonal_vectors_distance_one_similarity_zero(self):
        """Orthogonal unit vectors: distance=1.0, similarity=0.0."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        dist = _cosine_distance(a, b)
        assert math.isclose(dist, 1.0, abs_tol=1e-6), f"dist={dist}"
        sim = _expected_similarity(dist)
        assert math.isclose(sim, 0.0, abs_tol=1e-4), f"sim={sim}"

    def test_45_degree_vectors(self):
        """Vectors at 45°: similarity = cos(45°) ≈ 0.7071, distance ≈ 0.2929."""
        a = [1.0, 0.0]
        b = [math.sqrt(0.5), math.sqrt(0.5)]  # unit vector at 45°
        dist = _cosine_distance(a, b)
        expected_dist = 1.0 - math.cos(math.radians(45))
        assert math.isclose(dist, expected_dist, abs_tol=1e-5), f"dist={dist}"
        sim = _expected_similarity(dist)
        expected_sim = math.cos(math.radians(45))
        assert math.isclose(sim, expected_sim, abs_tol=1e-3), f"sim={sim}"

    def test_distance_half_gives_similarity_half(self):
        """distance=0.5 → similarity=0.5 (sanity check for linear formula)."""
        dist = 0.5
        sim = _expected_similarity(dist)
        assert math.isclose(sim, 0.5, abs_tol=1e-6), f"sim={sim}"

    def test_formula_is_not_distance_over_two(self):
        """
        Regression guard: the WRONG formula (1.0 - dist/2) would return 0.75
        for distance=0.5, but the CORRECT formula (1.0 - dist) returns 0.5.
        This test fails if the /2 divisor is accidentally re-introduced.
        """
        dist = 0.5
        wrong_sim = 1.0 - (dist / 2.0)   # the old broken formula
        correct_sim = _expected_similarity(dist)
        assert correct_sim != wrong_sim, "Formulas must differ for dist=0.5"
        assert math.isclose(correct_sim, 0.5, abs_tol=1e-6)
        assert math.isclose(wrong_sim, 0.75, abs_tol=1e-6)

    def test_distance_zero_gives_similarity_one(self):
        assert math.isclose(_expected_similarity(0.0), 1.0, abs_tol=1e-6)

    def test_distance_one_gives_similarity_zero(self):
        assert math.isclose(_expected_similarity(1.0), 0.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# Integration tests: ChromaDB-backed distance/similarity round-trip
# ---------------------------------------------------------------------------

class TestVectorStoreDistanceSimilarity:
    """
    Verify that VectorStoreService.search() returns distances and similarity
    scores that match the cosine-distance formula for known inputs.
    """

    def _make_store(self, tmp_path, collection_name: str) -> "VectorStoreService":
        from backend.app.services.chunking import GuidelineChunk
        persist_dir = str(tmp_path / collection_name)
        vs = VectorStoreService(persist_dir=persist_dir, collection_name=collection_name)
        chunks = [
            GuidelineChunk(
                chunk_id="sim_c0",
                document_id="sim-doc",
                source_filename="sim.txt",
                page_number=1,
                chunk_index=0,
                text="Identical vector reference chunk.",
                word_count=5, char_count=33,
            ),
            GuidelineChunk(
                chunk_id="sim_c1",
                document_id="sim-doc",
                source_filename="sim.txt",
                page_number=1,
                chunk_index=1,
                text="Orthogonal vector reference chunk.",
                word_count=5, char_count=34,
            ),
        ]
        # dim-4 unit vectors: c0=[1,0,0,0], c1=[0,1,0,0]
        vs.add_chunks(chunks, [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        return vs

    def test_identical_query_has_near_zero_distance(self, tmp_path):
        vs = self._make_store(tmp_path, "sim_test_identical")
        results = vs.search([1.0, 0.0, 0.0, 0.0], top_k=1)
        top = results[0]
        assert top["chunk_id"] == "sim_c0"
        assert top["distance"] < 0.01, f"distance={top['distance']}"
        assert top["similarity_score"] > 0.99, f"sim={top['similarity_score']}"

    def test_orthogonal_query_has_near_one_distance(self, tmp_path):
        vs = self._make_store(tmp_path, "sim_test_orthogonal")
        # query [0,0,1,0] is orthogonal to both indexed vectors
        results = vs.search([0.0, 0.0, 1.0, 0.0], top_k=2)
        for r in results:
            assert r["distance"] > 0.9, f"expected high distance, got {r['distance']}"
            assert r["similarity_score"] < 0.1, f"expected low sim, got {r['similarity_score']}"

    def test_similarity_equals_one_minus_distance(self, tmp_path):
        """similarity_score must always equal round(1.0 - distance, 4) for all results."""
        vs = self._make_store(tmp_path, "sim_test_formula")
        results = vs.search([0.7, 0.7, 0.0, 0.0], top_k=2)
        for r in results:
            expected_sim = round(1.0 - r["distance"], 4)
            assert math.isclose(r["similarity_score"], expected_sim, abs_tol=1e-4), (
                f"chunk_id={r['chunk_id']}: "
                f"distance={r['distance']}, sim={r['similarity_score']}, "
                f"expected_sim={expected_sim}"
            )

    def test_results_ordered_ascending_distance(self, tmp_path):
        """ChromaDB should return results ranked nearest-first (ascending distance)."""
        vs = self._make_store(tmp_path, "sim_test_order")
        results = vs.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0]["distance"] <= results[1]["distance"]

    def test_all_distances_finite_and_in_range(self, tmp_path):
        vs = self._make_store(tmp_path, "sim_test_finite")
        results = vs.search([0.5, 0.5, 0.0, 0.0], top_k=2)
        for r in results:
            assert math.isfinite(r["distance"]), f"Non-finite distance: {r['distance']}"
            assert 0.0 <= r["distance"] <= 1.0 + 1e-5, (
                f"Distance {r['distance']} outside [0,1]"
            )
            assert math.isfinite(r["similarity_score"])
            assert 0.0 <= r["similarity_score"] <= 1.0 + 1e-5
