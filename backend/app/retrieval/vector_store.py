"""
ChromaDB Persistent Vector Store Service for BrandSentry AI.
Manages persistent collection storage, idempotent chunk upserts, and metadata filtering.

Distance / Similarity Semantics
--------------------------------
The collection is created with ``metadata={"hnsw:space": "cosine"}``, which instructs
ChromaDB's HNSW index to use **cosine distance**.

ChromaDB's cosine distance is defined as::

    cosine_distance = 1 - cosine_similarity

This means the distance is bounded in **[0, 1]** for unit-normalised vectors:
- 0.0  → vectors are identical  (cosine similarity = 1.0)
- 1.0  → vectors are orthogonal (cosine similarity = 0.0)

Note: the range is NOT [0, 2].  The ``/ 2`` divisor sometimes seen in the literature
applies to a different convention (e.g. angular distance scaled from [-1, 1]).  Do
*not* apply that divisor here — it would silently inflate similarity scores.

Conventional cosine similarity is therefore recovered as::

    cosine_similarity = 1.0 - distance

This similarity is used only for **ranking / comparison** and must NEVER be presented
as a compliance confidence, correctness probability, or truth probability.
"""
import math
import os
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.services.chunking import GuidelineChunk

logger = logging.getLogger(__name__)

# Metric used by this service's ChromaDB collection.
# Changing this constant requires a full re-index of all persistent data.
_CHROMA_DISTANCE_METRIC: str = "cosine"


class VectorStoreService:
    """
    Manages persistent ChromaDB vector collections for brand guidelines.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        if persist_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.persist_dir = os.path.abspath(os.path.join(base_dir, "data", "chroma"))
        else:
            self.persist_dir = os.path.abspath(persist_dir)

        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        os.makedirs(self.persist_dir, exist_ok=True)
        self._client = None
        self._collection = None

    @property
    def client(self):
        """Lazy loader for persistent ChromaDB client."""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            logger.info("Initializing ChromaDB PersistentClient at '%s'...", self.persist_dir)
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
        return self._client

    @property
    def collection(self):
        """
        Lazy loader for the named guideline chunks collection.

        Distance metric: ``cosine`` (see module docstring for semantics).
        Embeddings are provided pre-computed by EmbeddingService; ChromaDB's
        built-in embedding function is intentionally not used here.
        """
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": _CHROMA_DISTANCE_METRIC},
            )
            logger.info(
                "Opened ChromaDB collection '%s' (distance metric: %s).",
                self.collection_name,
                _CHROMA_DISTANCE_METRIC,
            )
        return self._collection

    def add_chunks(
        self,
        chunks: List[GuidelineChunk],
        embeddings: List[List[float]],
    ) -> int:
        """
        Idempotently indexes guideline chunks and their embeddings into ChromaDB.
        Uses upsert to safely support re-indexing and prevent duplicate key errors.
        """
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch between chunks count ({len(chunks)}) and embeddings count ({len(embeddings)})."
            )

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "source_filename": c.source_filename,
                "page_number": c.page_number if c.page_number is not None else 1,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]

        # Use upsert to guarantee idempotency
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "Successfully upserted %d chunks into collection '%s'.",
            len(chunks),
            self.collection_name,
        )
        return len(chunks)

    def search(
        self,
        query_embedding: List[float],
        document_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic nearest-neighbor search against the persistent vector store.
        Optionally filters results by document_id.
        """
        where_filter = {"document_id": document_id} if document_id else None

        # Guard against top_k greater than collection count
        total_items = self.collection.count()
        if total_items == 0:
            return []

        effective_k = min(top_k, total_items)

        query_args: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": effective_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_args["where"] = where_filter

        results = self.collection.query(**query_args)

        matches: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return matches

        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i in range(len(ids)):
            raw_dist = float(distances[i]) if i < len(distances) else 0.0

            # Validate: ChromaDB cosine distance must be a finite number in [0, 1].
            # Any other value indicates a serious indexing or configuration problem.
            if not math.isfinite(raw_dist):
                logger.error(
                    "Non-finite cosine distance (%s) returned for chunk '%s'. "
                    "This indicates an indexing problem. Skipping result.",
                    raw_dist,
                    ids[i],
                )
                continue
            if raw_dist < 0.0 or raw_dist > 1.0 + 1e-6:
                logger.warning(
                    "Cosine distance %s for chunk '%s' is outside expected [0, 1] range. "
                    "Clamping for display but this may signal a metric mismatch.",
                    raw_dist,
                    ids[i],
                )

            # ChromaDB cosine distance is defined as:  distance = 1 - cosine_similarity
            # Therefore:  cosine_similarity = 1.0 - distance
            # Range: distance 0.0 → similarity 1.0 (identical)
            #        distance 1.0 → similarity 0.0 (orthogonal)
            # This similarity is for RANKING ONLY — not compliance confidence.
            dist = max(0.0, min(raw_dist, 1.0))  # clamp only after logging
            sim_score = round(1.0 - dist, 4)

            meta = metas[i] if i < len(metas) else {}
            matches.append(
                {
                    "chunk_id": ids[i],
                    "document_id": meta.get("document_id", ""),
                    "source_filename": meta.get("source_filename", ""),
                    "page_number": meta.get("page_number"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "text": docs[i] if i < len(docs) else "",
                    "distance": round(raw_dist, 4),
                    "similarity_score": sim_score,
                }
            )

        return matches

    def delete_document(self, document_id: str) -> None:
        """Deletes all chunks associated with a specific document_id."""
        self.collection.delete(where={"document_id": document_id})

    def count(self) -> int:
        """Returns total chunks currently indexed in collection."""
        return self.collection.count()


vector_store_service = VectorStoreService()
