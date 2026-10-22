"""
ChromaDB Persistent Vector Store Service for BrandSentry AI.
Manages persistent collection storage, idempotent chunk upserts, and metadata filtering.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.services.chunking import GuidelineChunk

logger = logging.getLogger(__name__)


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
        """Lazy loader for the named guideline chunks collection."""
        if self._collection is None:
            # We provide precomputed embeddings from EmbeddingService
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
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
            dist = float(distances[i]) if i < len(distances) else 0.0
            # For cosine space in ChromaDB, distance is in [0, 2] where 0 is identical
            # Normalized similarity score for comparison ranking: max(0.0, 1.0 - dist)
            sim_score = max(0.0, round(1.0 - (dist / 2.0), 4))

            meta = metas[i] if i < len(metas) else {}
            matches.append(
                {
                    "chunk_id": ids[i],
                    "document_id": meta.get("document_id", ""),
                    "source_filename": meta.get("source_filename", ""),
                    "page_number": meta.get("page_number"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "text": docs[i] if i < len(docs) else "",
                    "distance": round(dist, 4),
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
