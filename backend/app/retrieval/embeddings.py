"""
Embedding Generation Service for BrandSentry AI.
Generates local, CPU-friendly dense vector embeddings for 'all-MiniLM-L6-v2' (384 dimensions).
Model is loaded lazily and reused across requests.
"""
import logging
from typing import List, Optional
import numpy as np
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Singleton service managing local CPU dense vector embeddings.
    Uses 'all-MiniLM-L6-v2' via ONNXRuntime/ChromaDB DefaultEmbeddingFunction
    or SentenceTransformers with lazy loading and memory caching.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._embed_fn = None
        self._dimension = 384

    @property
    def embed_fn(self):
        """Lazy loader for embedding engine."""
        if self._embed_fn is None:
            logger.info("Initializing embedding engine for '%s' on CPU...", self.model_name)
            try:
                # 1. Prefer Chroma's optimized ONNX all-MiniLM-L6-v2 engine (CPU only, fast)
                from chromadb.utils import embedding_functions
                self._embed_fn = embedding_functions.DefaultEmbeddingFunction()
                # Warm-up / verify
                sample = self._embed_fn(["Brand compliance warm-up test"])
                self._dimension = len(sample[0])
                logger.info(
                    "ONNX Embedding engine loaded successfully. Model: %s, Dimension: %d",
                    self.model_name,
                    self._dimension,
                )
            except Exception as onnx_err:
                logger.warning(
                    "Default ONNX embedding function not immediately available (%s). Trying SentenceTransformers...",
                    onnx_err,
                )
                try:
                    import importlib
                    st_module = importlib.import_module("sentence_transformers")
                    SentenceTransformer = getattr(st_module, "SentenceTransformer")
                    st_model = SentenceTransformer(self.model_name, device="cpu")
                    self._embed_fn = lambda texts: st_model.encode(
                        texts, normalize_embeddings=True, convert_to_numpy=True
                    ).tolist()
                    sample = self._embed_fn(["Brand compliance warm-up test"])
                    self._dimension = len(sample[0])
                    logger.info(
                        "SentenceTransformers embedding model loaded on CPU. Model: %s, Dimension: %d",
                        self.model_name,
                        self._dimension,
                    )
                except Exception as st_err:
                    logger.error(
                        "Failed to initialize embedding model '%s': ONNX err: %s; ST err: %s",
                        self.model_name,
                        onnx_err,
                        st_err,
                    )
                    raise RuntimeError(
                        f"Could not load local embedding model '{self.model_name}'. "
                        f"Error: {st_err or onnx_err}"
                    ) from st_err
        return self._embed_fn

    @property
    def dimension(self) -> int:
        """Returns the vector dimensionality of the model (384)."""
        return self._dimension

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates normalized dense embeddings for a list of text strings.
        Validates output to ensure values are non-empty and finite.
        """
        if not texts:
            return []

        # Filter empty or whitespace-only texts while preserving indices
        processed_texts = [t.strip() if t.strip() else " " for t in texts]

        try:
            raw_embeddings = self.embed_fn(processed_texts)
        except Exception as exc:
            raise RuntimeError(f"Embedding generation failed: {str(exc)}") from exc

        embeddings_np = np.array(raw_embeddings, dtype=np.float32)

        # Validation: check non-empty and finite
        if not np.all(np.isfinite(embeddings_np)):
            raise ValueError("Generated embeddings contain non-finite values (NaN or Inf).")

        # Normalize to unit length for cosine metric consistency
        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = embeddings_np / norms

        return normalized.tolist()

    def generate_query_embedding(self, query: str) -> List[float]:
        """Generates embedding for a single query string."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty for embedding generation.")

        embeddings = self.generate_embeddings([query])
        return embeddings[0]


embedding_service = EmbeddingService()
