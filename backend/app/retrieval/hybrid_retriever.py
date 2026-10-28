"""
Hybrid Document Retriever for BrandSentry AI.
Combines Dense Semantic Vector Search (ChromaDB + all-MiniLM-L6-v2)
with Sparse Lexical Search (BM25Okapi) using Reciprocal Rank Fusion (RRF).
"""
import re
import logging
from typing import List, Dict, Any, Optional

from backend.app.core.config import settings
from backend.app.retrieval.vector_store import vector_store_service, VectorStoreService
from backend.app.retrieval.bm25_retriever import bm25_retriever, BM25RetrieverService
from backend.app.retrieval.embeddings import embedding_service, EmbeddingService

logger = logging.getLogger(__name__)


class HybridRetrieverService:
    """
    Hybrid retriever that unifies semantic vector search and BM25 keyword search.
    Calculates fused candidate ranks using Reciprocal Rank Fusion:
        RRF(d) = sum(1.0 / (k + rank(d)))
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreService] = None,
        bm25_service: Optional[BM25RetrieverService] = None,
        embeddings: Optional[EmbeddingService] = None,
        smoothing_k: Optional[int] = None,
    ):
        self.vector_store = vector_store or vector_store_service
        self.bm25 = bm25_service or bm25_retriever
        self.embeddings = embeddings or embedding_service
        self.smoothing_k = smoothing_k if smoothing_k is not None else settings.RRF_SMOOTHING_K

    def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        query_embedding: Optional[List[float]] = None,
        mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k evidence passages for a given query or claim.

        Args:
            query: Natural language query or claim text.
            document_id: Optional single document ID filter.
            document_ids: Optional list of document IDs for multi-document scoping.
            top_k: Number of final passages to return.
            query_embedding: Optional pre-computed query embedding.
            mode: Retrieval mode ('hybrid', 'dense', or 'bm25'). Defaults to settings.RETRIEVAL_MODE.

        Returns:
            List of passage dicts sorted by relevance, with metadata and scores.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            return []

        active_mode = (mode or settings.RETRIEVAL_MODE).lower()

        # Build list of scoped document IDs
        target_doc_ids: Optional[List[str]] = None
        if document_ids:
            target_doc_ids = list(document_ids)
        elif document_id:
            target_doc_ids = [document_id]

        if active_mode == "dense":
            return self._dense_search(clean_query, target_doc_ids, top_k, query_embedding)
        elif active_mode == "bm25":
            return self._bm25_search(clean_query, target_doc_ids, top_k)
        else:
            return self._hybrid_search(clean_query, target_doc_ids, top_k, query_embedding)

    def _dense_search(
        self,
        query: str,
        target_doc_ids: Optional[List[str]],
        top_k: int,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Runs dense-only semantic search."""
        if query_embedding is None:
            query_embedding = self.embeddings.generate_query_embedding(query)

        raw_results: List[Dict[str, Any]] = []
        if not target_doc_ids:
            raw_results = self.vector_store.search(
                query_embedding=query_embedding,
                document_id=None,
                top_k=top_k * 2,
            )
        else:
            for doc_id in target_doc_ids:
                matches = self.vector_store.search(
                    query_embedding=query_embedding,
                    document_id=doc_id,
                    top_k=top_k,
                )
                for m in matches:
                    if m.get("document_id") == doc_id:
                        raw_results.append(m)

        raw_results.sort(key=lambda x: x.get("distance", 1.0))
        return self._deduplicate_passages(raw_results, top_k)

    def _bm25_search(
        self,
        query: str,
        target_doc_ids: Optional[List[str]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Runs BM25-only lexical search."""
        raw_results: List[Dict[str, Any]] = []
        if not target_doc_ids:
            raw_results = self.bm25.search(
                query=query,
                document_id=None,
                top_k=top_k * 2,
            )
        else:
            for doc_id in target_doc_ids:
                matches = self.bm25.search(
                    query=query,
                    document_id=doc_id,
                    top_k=top_k,
                )
                for m in matches:
                    if m.get("document_id") == doc_id:
                        raw_results.append(m)

        raw_results.sort(key=lambda x: x.get("bm25_score", 0.0), reverse=True)
        # Format distance/similarity fields for compatibility
        for r in raw_results:
            if "similarity_score" not in r:
                r["distance"] = round(1.0 / (1.0 + r.get("bm25_score", 1.0)), 4)
                r["similarity_score"] = round(1.0 - r["distance"], 4)

        return self._deduplicate_passages(raw_results, top_k)

    def _hybrid_search(
        self,
        query: str,
        target_doc_ids: Optional[List[str]],
        top_k: int,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Combines dense vector search and BM25 lexical search via Reciprocal Rank Fusion (RRF).
        RRF formula: RRF_score(d) = sum(1.0 / (k + rank_i(d)))
        """
        candidate_pool_size = max(top_k * 3, 15)

        # 1. Retrieve dense candidates
        dense_candidates = self._dense_search(
            query=query,
            target_doc_ids=target_doc_ids,
            top_k=candidate_pool_size,
            query_embedding=query_embedding,
        )

        # 2. Retrieve BM25 candidates
        bm25_candidates = self._bm25_search(
            query=query,
            target_doc_ids=target_doc_ids,
            top_k=candidate_pool_size,
        )

        # 3. Fuse with RRF
        k = self.smoothing_k
        fused_scores: Dict[str, float] = {}
        candidate_meta: Dict[str, Dict[str, Any]] = {}

        # Process dense ranks (1-indexed)
        for rank, item in enumerate(dense_candidates, start=1):
            cid = item["chunk_id"]
            rrf_val = 1.0 / (k + rank)
            fused_scores[cid] = fused_scores.get(cid, 0.0) + rrf_val
            if cid not in candidate_meta:
                candidate_meta[cid] = dict(item)
            else:
                candidate_meta[cid].setdefault("similarity_score", item.get("similarity_score"))
                candidate_meta[cid].setdefault("distance", item.get("distance"))

        # Process BM25 ranks (1-indexed)
        for rank, item in enumerate(bm25_candidates, start=1):
            cid = item["chunk_id"]
            rrf_val = 1.0 / (k + rank)
            fused_scores[cid] = fused_scores.get(cid, 0.0) + rrf_val
            if cid not in candidate_meta:
                candidate_meta[cid] = dict(item)
            candidate_meta[cid]["bm25_score"] = item.get("bm25_score", 0.0)

        # Build combined scored candidate list
        merged_candidates: List[Dict[str, Any]] = []
        for cid, rrf_score in fused_scores.items():
            meta = candidate_meta[cid]
            meta["rrf_score"] = round(rrf_score, 6)
            # Ensure similarity_score and distance are populated
            if "similarity_score" not in meta or meta["similarity_score"] is None:
                meta["similarity_score"] = 0.50
                meta["distance"] = 0.50
            merged_candidates.append(meta)

        # Sort primarily by descending RRF score, secondary by similarity_score
        merged_candidates.sort(
            key=lambda x: (x.get("rrf_score", 0.0), x.get("similarity_score", 0.0)),
            reverse=True,
        )

        return self._deduplicate_passages(merged_candidates, top_k)

    def _deduplicate_passages(
        self,
        passages: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Removes exact and near-identical passage duplicates."""
        seen_chunk_ids = set()
        seen_texts = set()
        deduped: List[Dict[str, Any]] = []

        for p in passages:
            cid = p.get("chunk_id", "")
            if cid in seen_chunk_ids:
                continue

            raw_text = p.get("text", "").strip()
            norm_text = re.sub(r"\s+", " ", raw_text.lower())
            if norm_text in seen_texts:
                continue

            seen_chunk_ids.add(cid)
            seen_texts.add(norm_text)
            deduped.append(p)

            if len(deduped) >= top_k:
                break

        return deduped


hybrid_retriever = HybridRetrieverService()
