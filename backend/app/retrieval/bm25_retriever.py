"""
BM25 Lexical Retriever Module for BrandSentry AI.
Provides fast, exact-match and keyword-aware document retrieval using BM25Okapi.
Maintains persistent index of guideline passages synchronized with ChromaDB vector store.
"""
import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

from backend.app.core.config import settings
from backend.app.services.chunking import GuidelineChunk

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """Tokenizes text into normalized lowercased word tokens."""
    if not text:
        return []
    return re.findall(r"\b\w+\b", text.lower())


class BM25RetrieverService:
    """
    Persistent lexical retrieval service using BM25Okapi.
    Indexes guideline chunks alongside vector embeddings, preserving chunk metadata,
    source document scoping, and stable IDs across system restarts.
    """

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir is None:
            self.persist_dir = os.path.abspath(settings.bm25_persist_dir)
        else:
            self.persist_dir = os.path.abspath(persist_dir)

        os.makedirs(self.persist_dir, exist_ok=True)
        self.store_file = os.path.join(self.persist_dir, "bm25_chunks.json")

        # In-memory chunk registry: chunk_id -> dict
        self._chunks: Dict[str, Dict[str, Any]] = {}
        self._bm25_model: Optional[BM25Okapi] = None
        self._indexed_chunk_ids: List[str] = []

        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Loads indexed chunks from persistent disk storage if available."""
        if not os.path.exists(self.store_file):
            return

        try:
            with open(self.store_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "chunk_id" in item:
                            self._chunks[item["chunk_id"]] = item
            self._rebuild_bm25_model()
            logger.info("Loaded %d BM25 chunks from %s", len(self._chunks), self.store_file)
        except Exception as exc:
            logger.warning("Failed to load BM25 index from disk (%s): %s", self.store_file, exc)

    def _persist_to_disk(self) -> None:
        """Saves current chunks to persistent JSON store."""
        try:
            temp_file = f"{self.store_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(list(self._chunks.values()), f, ensure_ascii=False, indent=2)
            if os.path.exists(self.store_file):
                os.replace(temp_file, self.store_file)
            else:
                os.rename(temp_file, self.store_file)
        except Exception as exc:
            logger.error("Failed to persist BM25 chunks to disk: %s", exc)

    def _rebuild_bm25_model(self) -> None:
        """Reconstructs the BM25Okapi model from current in-memory chunks."""
        if not self._chunks:
            self._bm25_model = None
            self._indexed_chunk_ids = []
            return

        self._indexed_chunk_ids = list(self._chunks.keys())
        tokenized_corpus = [
            _tokenize(self._chunks[cid].get("text", ""))
            for cid in self._indexed_chunk_ids
        ]
        self._bm25_model = BM25Okapi(tokenized_corpus)

    def add_chunks(self, chunks: List[GuidelineChunk]) -> int:
        """
        Idempotently adds or updates guideline chunks in the BM25 lexical index.
        Saves updated index to disk.
        """
        if not chunks:
            return 0

        for c in chunks:
            self._chunks[c.chunk_id] = {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "source_filename": c.source_filename,
                "page_number": c.page_number if c.page_number is not None else 1,
                "chunk_index": c.chunk_index,
                "text": c.text,
            }

        self._rebuild_bm25_model()
        self._persist_to_disk()
        logger.info("BM25 index updated with %d chunks (total: %d).", len(chunks), len(self._chunks))
        return len(chunks)

    def delete_document(self, document_id: str) -> int:
        """Removes all chunks associated with document_id and rebuilds BM25 model."""
        to_delete = [
            cid for cid, c in self._chunks.items()
            if c.get("document_id") == document_id
        ]
        for cid in to_delete:
            del self._chunks[cid]

        if to_delete:
            self._rebuild_bm25_model()
            self._persist_to_disk()
            logger.info("Removed %d chunks for document %s from BM25 index.", len(to_delete), document_id)
        return len(to_delete)

    def count(self) -> int:
        """Returns total number of chunks in the BM25 index."""
        return len(self._chunks)

    def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Searches lexical index using BM25Okapi.
        Supports document scoping, empty queries, and empty indexes.
        Returns matches ordered by BM25 score descending.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            return []

        if not self._bm25_model or not self._indexed_chunk_ids:
            return []

        tokens = _tokenize(clean_query)
        if not tokens:
            return []

        doc_scores = self._bm25_model.get_scores(tokens)

        # Pair scores with chunk metadata
        scored_candidates: List[Dict[str, Any]] = []
        for cid, score in zip(self._indexed_chunk_ids, doc_scores):
            # Only consider positive BM25 scores (at least one term match)
            if score <= 0.0:
                continue

            chunk_meta = self._chunks.get(cid)
            if not chunk_meta:
                continue

            if document_id and chunk_meta.get("document_id") != document_id:
                continue

            scored_candidates.append({
                "chunk_id": cid,
                "document_id": chunk_meta.get("document_id", ""),
                "source_filename": chunk_meta.get("source_filename", ""),
                "page_number": chunk_meta.get("page_number", 1),
                "chunk_index": chunk_meta.get("chunk_index", 0),
                "text": chunk_meta.get("text", ""),
                "bm25_score": round(float(score), 4),
            })

        # Sort by BM25 score descending
        scored_candidates.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored_candidates[:top_k]

    def reset(self) -> None:
        """Clears all in-memory chunks and deletes index file."""
        self._chunks.clear()
        self._bm25_model = None
        self._indexed_chunk_ids = []
        if os.path.exists(self.store_file):
            try:
                os.remove(self.store_file)
            except Exception as exc:
                logger.warning("Failed to delete BM25 store file: %s", exc)


bm25_retriever = BM25RetrieverService()
