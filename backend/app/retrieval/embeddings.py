"""
Embedding Generation Service for BrandSentry AI.

Model Identity
--------------
This service targets the ``all-MiniLM-L6-v2`` Sentence Transformer model, which
produces 384-dimensional dense vectors.  Two loading strategies are attempted in order:

1. **ChromaDB ONNX engine** (preferred): ``chromadb.utils.embedding_functions.DefaultEmbeddingFunction``
   which internally delegates to ``ONNXMiniLM_L6_V2``.  This is the same model
   (``all-MiniLM-L6-v2``) compiled for ONNXRuntime.  No GPU required.

2. **SentenceTransformers fallback**: loads the model directly via the
   ``sentence-transformers`` package with ``device="cpu"``.

Critical consistency rule
--------------------------
Both strategies produce embeddings from the *same* underlying model
(``all-MiniLM-L6-v2``, 384 dimensions).  Mixing embeddings from different models
in the same ChromaDB collection will silently corrupt retrieval quality.

If the configured ``EMBEDDING_MODEL_NAME`` does not equal ``all-MiniLM-L6-v2``
a ``RuntimeError`` is raised at initialization time rather than silently using a
mismatched model.

Normalization
-------------
Output embeddings are L2-normalised to unit length.  This is required for the
ChromaDB cosine-distance collection to work correctly (cosine distance is
well-defined only for non-zero vectors; unit-length vectors simplify the
arithmetic to  ``distance = 1 - dot(a, b)``).
"""
import logging
import math
import threading
from collections import OrderedDict
from typing import List, Optional, Dict
import numpy as np
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# The one and only model this service is designed to use.
# Changing this must be accompanied by a full re-index of all ChromaDB data.
_SUPPORTED_MODEL_NAME: str = "all-MiniLM-L6-v2"
_EXPECTED_DIMENSION: int = 384


class EmbeddingService:
    """
    Singleton service managing local CPU dense vector embeddings.

    Uses ``all-MiniLM-L6-v2`` via ChromaDB's ONNXRuntime engine or
    SentenceTransformers (fallback), with lazy loading and in-process caching.

    The active embedding engine and model name are logged at INFO level the
    first time embeddings are generated.
    """

    def __init__(self, model_name: Optional[str] = None):
        resolved = model_name or settings.EMBEDDING_MODEL_NAME

        # Refuse to start if the config points at a different model, which would
        # silently produce incompatible embeddings for existing ChromaDB data.
        if resolved != _SUPPORTED_MODEL_NAME:
            raise RuntimeError(
                f"EmbeddingService: configured EMBEDDING_MODEL_NAME='{resolved}' does not match "
                f"the only supported model '{_SUPPORTED_MODEL_NAME}'. "
                "Change the configuration or re-index all ChromaDB data before switching models."
            )

        self.model_name: str = resolved
        self._embed_fn = None
        self._active_engine: str = "uninitialised"
        self._dimension: int = _EXPECTED_DIMENSION
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._cache_max_size: int = 2048
        self._cache_lock = threading.Lock()

    @property
    def embed_fn(self):
        """Lazy loader for embedding engine.  Logs active engine and validates output shape."""
        if self._embed_fn is None:
            logger.info(
                "Initialising embedding engine for '%s' on CPU...", self.model_name
            )
            try:
                # 1. Prefer ChromaDB's optimised ONNX all-MiniLM-L6-v2 engine (fast, no GPU)
                from chromadb.utils import embedding_functions

                onnx_fn = embedding_functions.DefaultEmbeddingFunction()
                # Warm-up: verify the model produces the expected output shape
                sample = onnx_fn(["Brand compliance warm-up test"])
                actual_dim = len(sample[0])
                if actual_dim != _EXPECTED_DIMENSION:
                    raise RuntimeError(
                        f"ONNX engine returned dimension {actual_dim}, "
                        f"expected {_EXPECTED_DIMENSION} for '{self.model_name}'."
                    )
                self._embed_fn = onnx_fn
                self._dimension = actual_dim
                self._active_engine = f"ChromaDB-ONNX (ONNXMiniLM_L6_V2 / {self.model_name})"
                logger.info(
                    "Embedding engine: %s  Dimension: %d",
                    self._active_engine,
                    self._dimension,
                )
            except Exception as onnx_err:
                logger.warning(
                    "ChromaDB ONNX embedding engine not available (%s). "
                    "Falling back to SentenceTransformers...",
                    onnx_err,
                )
                try:
                    import importlib

                    st_module = importlib.import_module("sentence_transformers")
                    SentenceTransformer = getattr(st_module, "SentenceTransformer")
                    st_model = SentenceTransformer(self.model_name, device="cpu")

                    def _st_embed(texts: List[str]) -> List[List[float]]:
                        return (
                            st_model.encode(
                                texts,
                                normalize_embeddings=True,
                                convert_to_numpy=True,
                            ).tolist()
                        )

                    # Warm-up: verify model and dimension
                    sample = _st_embed(["Brand compliance warm-up test"])
                    actual_dim = len(sample[0])
                    if actual_dim != _EXPECTED_DIMENSION:
                        raise RuntimeError(
                            f"SentenceTransformers returned dimension {actual_dim}, "
                            f"expected {_EXPECTED_DIMENSION} for '{self.model_name}'."
                        )
                    self._embed_fn = _st_embed
                    self._dimension = actual_dim
                    self._active_engine = f"SentenceTransformers (CPU / {self.model_name})"
                    logger.info(
                        "Embedding engine: %s  Dimension: %d",
                        self._active_engine,
                        self._dimension,
                    )
                except Exception as st_err:
                    raise RuntimeError(
                        f"Could not initialise local embedding model '{self.model_name}'. "
                        f"ONNX error: {onnx_err}. "
                        f"SentenceTransformers error: {st_err}. "
                        "Install onnxruntime and tokenizers (for ChromaDB ONNX) or "
                        "sentence-transformers (for the fallback path)."
                    ) from st_err
        return self._embed_fn

    @property
    def dimension(self) -> int:
        """Returns the vector dimensionality of the active model (384 for all-MiniLM-L6-v2)."""
        return self._dimension

    @property
    def active_engine(self) -> str:
        """Human-readable description of the active embedding engine (after first call)."""
        return self._active_engine

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates L2-normalised dense embeddings for a list of text strings.

        Validates that every output vector is:
        - Non-empty
        - The expected dimensionality (384)
        - Finite (no NaN or Inf values)
        - Non-zero (required for cosine-distance collections)

        Args:
            texts: List of non-empty strings to embed.

        Returns:
            List of 384-dimensional float vectors, each normalised to unit L2 length.

        Raises:
            RuntimeError: If the embedding engine fails or returns invalid output.
            ValueError: If the output contains non-finite values.
        """
        if not texts:
            return []

        # Replace empty/whitespace-only strings with a single space to avoid
        # embedding-engine errors; the caller should avoid submitting such texts.
        processed_texts = [t.strip() if t.strip() else " " for t in texts]

        # 1. Check cache for already-computed embeddings
        result_embeddings: List[Optional[List[float]]] = [None] * len(processed_texts)
        missing_indices: List[int] = []
        missing_texts_map: Dict[str, List[int]] = {}

        with self._cache_lock:
            for i, text in enumerate(processed_texts):
                cached_vec = self._cache.get(text)
                if cached_vec is not None:
                    result_embeddings[i] = cached_vec
                    self._cache.move_to_end(text)
                else:
                    if text not in missing_texts_map:
                        missing_texts_map[text] = []
                    missing_texts_map[text].append(i)

        # 2. If any texts are missing from cache, generate them in a single batch pass
        if missing_texts_map:
            unique_missing_texts = list(missing_texts_map.keys())
            try:
                raw_embeddings = self.embed_fn(unique_missing_texts)
            except Exception as exc:
                raise RuntimeError(f"Embedding generation failed: {exc}") from exc

            embeddings_np = np.array(raw_embeddings, dtype=np.float32)

            if embeddings_np.ndim != 2 or embeddings_np.shape[1] != _EXPECTED_DIMENSION:
                raise RuntimeError(
                    f"Embedding engine returned unexpected shape {embeddings_np.shape}; "
                    f"expected (n, {_EXPECTED_DIMENSION})."
                )

            if not np.all(np.isfinite(embeddings_np)):
                raise ValueError(
                    "Generated embeddings contain non-finite values (NaN or Inf). "
                    f"Active engine: {self._active_engine}."
                )

            # L2-normalise to unit length for cosine-distance correctness.
            norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
            zero_norm_mask = norms[:, 0] == 0.0
            if zero_norm_mask.any():
                logger.warning(
                    "%d zero-norm embedding(s) detected; replacing with zero vectors. "
                    "Check input texts for degenerate content.",
                    zero_norm_mask.sum(),
                )
                norms[zero_norm_mask] = 1.0  # avoid divide-by-zero; result stays zero vector
            normalized = (embeddings_np / norms).tolist()

            # Populate results and update LRU cache under lock
            with self._cache_lock:
                for text, norm_vec in zip(unique_missing_texts, normalized):
                    indices = missing_texts_map[text]
                    for idx in indices:
                        result_embeddings[idx] = norm_vec
                    self._cache[text] = norm_vec
                    if len(self._cache) > self._cache_max_size:
                        self._cache.popitem(last=False)

        return [vec for vec in result_embeddings if vec is not None]

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generates a single normalised embedding vector for a query string.

        Uses the same model and normalisation as ``generate_embeddings`` to
        guarantee that query vectors and document vectors are comparable.

        Args:
            query: A non-empty, non-whitespace-only string.

        Returns:
            384-dimensional float vector normalised to unit L2 length.

        Raises:
            ValueError: If query is empty or whitespace-only.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty for embedding generation.")

        embeddings = self.generate_embeddings([query])
        return embeddings[0]


embedding_service = EmbeddingService()
