"""
FastAPI Router for Phase 3 — Marketing Content Review Endpoint.

POST /api/review
    Accepts marketing text and optional guideline document IDs.
    Extracts claims, retrieves guideline evidence, classifies each claim,
    and returns a structured compliance verdict response.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status

from backend.app.core.config import settings
from backend.app.schemas.review import (
    ReviewRequest,
    ReviewResponse,
    ClaimVerdictSchema,
    EvidenceItemSchema,
    ReviewSummary,
)
from backend.app.services.document_registry import document_registry
from backend.app.services.claim_extractor import claim_extractor
from backend.app.services.verdict_engine import (
    verdict_engine,
    VERDICT_SUPPORTED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
)
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.vector_store import vector_store_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit marketing content for evidence-grounded compliance review",
    description=(
        "Extracts discrete claims from marketing copy, retrieves matching guideline passages "
        "from ChromaDB, and produces SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE verdicts "
        "for each claim.  Every verdict is grounded in real retrieved text — no citations are fabricated."
    ),
)
async def review_marketing_content(request: ReviewRequest):
    """
    Full Phase 3 review pipeline:
    1. Validate request (content length, document IDs).
    2. Extract claims deterministically.
    3. For each claim: embed → retrieve evidence → classify → build verdict.
    4. Return aggregated ReviewResponse.
    """
    content = request.content.strip()

    # --- 1. Input validation ---
    if len(content) > settings.MAX_REVIEW_CONTENT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Content exceeds maximum length of {settings.MAX_REVIEW_CONTENT_LENGTH} characters. "
                f"Submitted: {len(content)} characters."
            ),
        )

    # Validate document_ids if provided
    validated_doc_ids: List[str] = []
    if request.document_ids:
        for doc_id in request.document_ids:
            doc = document_registry.get_document(doc_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Guideline document '{doc_id}' not found in registry.",
                )
            if doc["status"] != "indexed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Guideline document '{doc_id}' has status '{doc['status']}' "
                        "and is not ready for evidence retrieval."
                    ),
                )
            validated_doc_ids.append(doc_id)

    review_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    # Log review initiation WITHOUT the full content to avoid logging sensitive data
    logger.info(
        "Review %s initiated: %d chars, %d document_ids.",
        review_id, len(content), len(validated_doc_ids),
    )

    # --- 2. Check if any guidelines are indexed ---
    total_indexed = vector_store_service.count()
    warning: Optional[str] = None
    if total_indexed == 0:
        warning = (
            "No guideline passages are currently indexed. "
            "Upload brand guidelines first to enable evidence-grounded verdicts. "
            "All claims will return INSUFFICIENT_EVIDENCE."
        )

    # --- 3. Extract claims ---
    try:
        claims = claim_extractor.extract(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # --- 4. Process each claim ---
    claim_verdicts: List[ClaimVerdictSchema] = []

    for claim in claims:
        try:
            passages = _retrieve_evidence(claim.claim_text, validated_doc_ids)
        except Exception as exc:
            logger.error(
                "Evidence retrieval failed for claim '%s' in review %s: %s",
                claim.claim_id, review_id, exc,
            )
            # Safe fallback: INSUFFICIENT_EVIDENCE rather than crash
            passages = []

        cv = verdict_engine.classify(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            retrieved_passages=passages,
        )

        # Map internal ClaimVerdict → schema
        evidence_schemas = [
            EvidenceItemSchema(
                chunk_id=e.chunk_id,
                document_id=e.document_id,
                source_filename=e.source_filename,
                page_number=e.page_number,
                quote=e.quote,
                similarity_score=round(e.similarity_score, 4),
                distance=round(e.distance, 4),
            )
            for e in cv.evidence
        ]

        claim_verdicts.append(
            ClaimVerdictSchema(
                claim_id=cv.claim_id,
                claim_text=cv.claim_text,
                verdict=cv.verdict,
                explanation=cv.explanation,
                evidence=evidence_schemas,
                suggested_correction=cv.suggested_correction,
                deterministic_rule_fired=cv.deterministic_rule_fired,
            )
        )

    # --- 5. Aggregate summary ---
    supported = sum(1 for v in claim_verdicts if v.verdict == VERDICT_SUPPORTED)
    contradicted = sum(1 for v in claim_verdicts if v.verdict == VERDICT_CONTRADICTED)
    insufficient = sum(1 for v in claim_verdicts if v.verdict == VERDICT_INSUFFICIENT)

    summary = ReviewSummary(
        total_claims=len(claim_verdicts),
        supported=supported,
        contradicted=contradicted,
        insufficient_evidence=insufficient,
    )

    return ReviewResponse(
        review_id=review_id,
        content_preview=content[:120] + ("…" if len(content) > 120 else ""),
        document_ids_searched=validated_doc_ids,
        claims=claim_verdicts,
        summary=summary,
        created_at=created_at,
        warning=warning,
    )


def _retrieve_evidence(
    claim_text: str,
    document_ids: List[str],
) -> list:
    """
    Embed the claim and retrieve top-k passages from ChromaDB.

    If document_ids is non-empty, one search is performed per document_id
    and results are merged, then deduplicated by chunk_id.
    If document_ids is empty, a single search across all documents is performed.
    """
    query_embedding = embedding_service.generate_query_embedding(claim_text)
    top_k = settings.REVIEW_EVIDENCE_TOP_K

    if not document_ids:
        return vector_store_service.search(
            query_embedding=query_embedding,
            document_id=None,
            top_k=top_k,
        )

    # Per-document search + merge + deduplicate
    seen_chunk_ids: set = set()
    merged: list = []
    for doc_id in document_ids:
        results = vector_store_service.search(
            query_embedding=query_embedding,
            document_id=doc_id,
            top_k=top_k,
        )
        for r in results:
            cid = r.get("chunk_id", "")
            if cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                merged.append(r)

    # Sort merged results by distance (nearest first)
    merged.sort(key=lambda x: x.get("distance", 1.0))
    return merged[:top_k]
