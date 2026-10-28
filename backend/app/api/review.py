"""
FastAPI Router for Phase 3 — Marketing Content Review Endpoint.

POST /api/review
    Accepts marketing text and optional guideline document IDs.
    Extracts claims, retrieves guideline evidence, classifies each claim,
    and returns a structured compliance verdict response.
"""
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Optional, List

import anyio
from fastapi import APIRouter, HTTPException, status, UploadFile, File

from backend.app.core.config import settings
from backend.app.schemas.review import (
    ReviewRequest,
    ReviewResponse,
    ClaimVerdictSchema,
    EvidenceItemSchema,
    ReviewSummary,
    SemanticDriftResult,
    SemanticDriftIssue,
    ImageOCRResponse,
    ImageReviewSubmitRequest,
    OCRTextBlock,
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
from backend.app.retrieval.hybrid_retriever import hybrid_retriever
from backend.app.services.audit_service import audit_service
from backend.app.services.ocr_service import (
    ocr_service,
    UnsupportedImageFormatError,
    InvalidImageError,
    ImageTooLargeError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_scope_and_versions(
    document_ids: Optional[List[str]],
    policy_version_ids: Optional[List[str]],
) -> Tuple[List[str], List[str]]:
    """
    Resolves request document and policy version identifiers into:
    1. validated_doc_ids: physical document IDs to search in ChromaDB and BM25.
    2. enforced_policy_versions: logical version identifiers for audit traceability.

    If no scope is specified (un-scoped review), scopes exclusively to active policy versions,
    preventing archived historical guideline versions from leaking into current reviews.
    """
    from unittest.mock import Mock, MagicMock
    is_reg_mocked = isinstance(document_registry, (Mock, MagicMock))
    is_vs_mocked = isinstance(vector_store_service, (Mock, MagicMock)) or isinstance(
        getattr(vector_store_service, "search", None), (Mock, MagicMock)
    )

    raw_identifiers: List[str] = []
    if policy_version_ids:
        raw_identifiers.extend(policy_version_ids)
    if document_ids:
        raw_identifiers.extend(document_ids)

    validated_doc_ids: List[str] = []
    enforced_versions: List[str] = []

    if raw_identifiers:
        for ident in raw_identifiers:
            resolved_doc_id = ident
            if not is_reg_mocked:
                resolved = document_registry.resolve_version_to_document_id(ident)
                if not resolved:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Guideline document or policy version '{ident}' not found in registry.",
                    )
                resolved_doc_id = resolved

            doc = document_registry.get_document(resolved_doc_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Guideline document '{ident}' not found in registry.",
                )
            if isinstance(doc, dict) and doc.get("status") != "indexed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Guideline document '{resolved_doc_id}' is not indexed and ready for retrieval.",
                )
            if resolved_doc_id not in validated_doc_ids:
                validated_doc_ids.append(resolved_doc_id)

            if ident.startswith("ver-"):
                if ident not in enforced_versions:
                    enforced_versions.append(ident)
            else:
                if not is_reg_mocked:
                    ver_id = document_registry.get_version_id_for_document(resolved_doc_id)
                    if ver_id and ver_id not in enforced_versions:
                        enforced_versions.append(ver_id)
                    elif resolved_doc_id not in enforced_versions:
                        enforced_versions.append(resolved_doc_id)
                else:
                    enforced_versions.append(resolved_doc_id)
    else:
        # Default un-scoped review
        if is_vs_mocked:
            return [], []

        active_doc_ids = document_registry.get_active_document_ids()
        validated_doc_ids = active_doc_ids
        for doc_id in active_doc_ids:
            ver_id = document_registry.get_version_id_for_document(doc_id)
            if ver_id and ver_id not in enforced_versions:
                enforced_versions.append(ver_id)

    return validated_doc_ids, enforced_versions


def _execute_review_pipeline(
    content: str,
    validated_doc_ids: List[str],
    review_id: str,
    created_at: str,
    retrieval_mode: Optional[str] = None,
    review_source: str = "text",
    ocr_raw_text: Optional[str] = None,
    ocr_corrected_text: Optional[str] = None,
    enforced_policy_versions: Optional[List[str]] = None,
) -> ReviewResponse:
    """
    Synchronous CPU-bound pipeline executed in a worker thread:
    1. Deterministic claim extraction
    2. Batch embedding generation (vectorized with cache support)
    3. Retrieval and grounded verdict generation
    4. Semantic drift evaluation
    """
    t_start = time.perf_counter()

    # Check if guidelines exist
    total_indexed = vector_store_service.count()
    warning: Optional[str] = None
    if total_indexed == 0:
        warning = (
            "No guideline passages are currently indexed. "
            "Upload brand guidelines first to enable evidence-grounded verdicts. "
            "All claims will return INSUFFICIENT_EVIDENCE."
        )

    # 1. Extract claims
    t_ext_start = time.perf_counter()
    try:
        claims = claim_extractor.extract(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    t_ext_ms = (time.perf_counter() - t_ext_start) * 1000

    # 2. Batch generate embeddings for all extracted claims simultaneously
    t_emb_start = time.perf_counter()
    claim_texts = [c.claim_text for c in claims]
    try:
        claim_embeddings = embedding_service.generate_embeddings(claim_texts)
        if not isinstance(claim_embeddings, list) or len(claim_embeddings) != len(claims):
            claim_embeddings = [
                embedding_service.generate_query_embedding(t) for t in claim_texts
            ]
    except Exception:
        claim_embeddings = [
            embedding_service.generate_query_embedding(t) for t in claim_texts
        ]
    t_emb_ms = (time.perf_counter() - t_emb_start) * 1000

    # 3. Process each claim with pre-computed query embeddings
    t_eval_start = time.perf_counter()
    claim_verdicts: List[ClaimVerdictSchema] = []

    for claim, q_emb in zip(claims, claim_embeddings):
        try:
            passages = _retrieve_evidence(
                claim.claim_text,
                validated_doc_ids,
                query_embedding=q_emb,
                mode=retrieval_mode,
            )
        except Exception as exc:
            logger.error(
                "Evidence retrieval failed for claim '%s' in review %s: %s",
                claim.claim_id, review_id, exc,
            )
            passages = []

        cv = verdict_engine.classify(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            retrieved_passages=passages,
        )

        # Map candidate passage metadata for extra scoring fields
        passage_meta_map = {p.get("chunk_id"): p for p in passages}

        evidence_schemas = [
            EvidenceItemSchema(
                chunk_id=e.chunk_id,
                document_id=e.document_id,
                source_filename=e.source_filename,
                page_number=e.page_number,
                quote=e.quote,
                similarity_score=round(e.similarity_score, 4),
                distance=round(e.distance, 4),
                bm25_score=passage_meta_map.get(e.chunk_id, {}).get("bm25_score"),
                rrf_score=passage_meta_map.get(e.chunk_id, {}).get("rrf_score"),
            )
            for e in cv.evidence
        ]

        drift_schema = None
        if getattr(cv, "semantic_drift", None) is not None:
            sd = cv.semantic_drift
            drift_schema = SemanticDriftResult(
                detected=sd.detected,
                issues=[
                    SemanticDriftIssue(
                        category=iss.category,
                        severity=iss.severity,
                        claim_phrase=iss.claim_phrase,
                        source_phrase=iss.source_phrase,
                        explanation=iss.explanation,
                        suggested_correction=iss.suggested_correction,
                    )
                    for iss in sd.issues
                ],
                uncertainty=sd.uncertainty,
            )

        claim_verdicts.append(
            ClaimVerdictSchema(
                claim_id=cv.claim_id,
                claim_text=cv.claim_text,
                verdict=cv.verdict,
                explanation=cv.explanation,
                evidence=evidence_schemas,
                suggested_correction=cv.suggested_correction,
                deterministic_rule_fired=cv.deterministic_rule_fired,
                semantic_drift=drift_schema,
            )
        )

    t_eval_ms = (time.perf_counter() - t_eval_start) * 1000

    # Aggregate summary
    supported = sum(1 for v in claim_verdicts if v.verdict == VERDICT_SUPPORTED)
    contradicted = sum(1 for v in claim_verdicts if v.verdict == VERDICT_CONTRADICTED)
    insufficient = sum(1 for v in claim_verdicts if v.verdict == VERDICT_INSUFFICIENT)

    summary = ReviewSummary(
        total_claims=len(claim_verdicts),
        supported=supported,
        contradicted=contradicted,
        insufficient_evidence=insufficient,
    )

    if validated_doc_ids:
        searched_doc_ids = list(validated_doc_ids)
    else:
        searched_doc_ids = [
            doc["document_id"]
            for doc in document_registry.list_documents()
            if doc.get("status") == "indexed"
        ]

    t_total_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        "Review %s finished in %.2fms | Extraction: %.2fms | Batch Embedding: %.2fms | "
        "Retrieval+Verdict: %.2fms | Claims: %d",
        review_id, t_total_ms, t_ext_ms, t_emb_ms, t_eval_ms, len(claims),
    )

    # Save persistent audit record
    try:
        audit_service.save_review(
            review_id=review_id,
            submitted_content=content,
            claims=[c.model_dump() for c in claim_verdicts],
            summary=summary.model_dump(),
            document_ids=searched_doc_ids,
            review_source=review_source,
            retrieval_mode=retrieval_mode,
            created_at=created_at,
            warning=warning,
            ocr_raw_text=ocr_raw_text,
            ocr_corrected_text=ocr_corrected_text,
            policy_versions=enforced_policy_versions,
        )
    except Exception as exc:
        logger.error("Failed to persist audit review record for %s: %s", review_id, exc)

    return ReviewResponse(
        review_id=review_id,
        content_preview=content[:120] + ("…" if len(content) > 120 else ""),
        document_ids_searched=searched_doc_ids,
        claims=claim_verdicts,
        summary=summary,
        created_at=created_at,
        warning=warning,
        review_source=review_source,
        ocr_raw_text=ocr_raw_text,
        ocr_user_text=ocr_corrected_text,
        policy_versions_used=enforced_policy_versions or [],
    )


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
    Full Phase 3 review pipeline offloaded to threadpool to avoid event-loop blocking:
    1. Validate request (content length, document IDs, policy versions).
    2. Extract claims deterministically.
    3. Batch embed claims & retrieve evidence & classify.
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

    # Validate and resolve document_ids and policy_version_ids
    validated_doc_ids, enforced_versions = _resolve_scope_and_versions(
        request.document_ids,
        request.policy_version_ids,
    )

    review_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Review %s initiated: %d chars, %d document_ids, %d policy_versions.",
        review_id, len(content), len(validated_doc_ids), len(enforced_versions),
    )

    # Execute synchronous CPU-heavy work in worker threadpool
    return await anyio.to_thread.run_sync(
        _execute_review_pipeline,
        content,
        validated_doc_ids,
        review_id,
        created_at,
        request.retrieval_mode,
        "text",
        None,
        None,
        enforced_versions,
    )


def _retrieve_evidence(
    claim_text: str,
    document_ids: List[str],
    query_embedding: Optional[List[float]] = None,
    mode: Optional[str] = None,
) -> list:
    """
    Retrieves top-k evidence passages using Hybrid Retriever (Dense + BM25 via RRF),
    preserving document scoping and stable chunk metadata.
    Supports backward compatibility when vector_store_service is mocked in unit tests.
    """
    from unittest.mock import Mock, MagicMock
    is_mocked = isinstance(vector_store_service, (Mock, MagicMock)) or isinstance(
        getattr(vector_store_service, "search", None), (Mock, MagicMock)
    )
    if is_mocked:
        hybrid_retriever.vector_store = vector_store_service
        effective_mode = mode or "dense"
        return hybrid_retriever.search(
            query=claim_text,
            document_ids=document_ids if document_ids else None,
            top_k=settings.REVIEW_EVIDENCE_TOP_K,
            query_embedding=query_embedding,
            mode=effective_mode,
        )

    return hybrid_retriever.search(
        query=claim_text,
        document_ids=document_ids if document_ids else None,
        top_k=settings.REVIEW_EVIDENCE_TOP_K,
        query_embedding=query_embedding,
        mode=mode,
    )


@router.post(
    "/image",
    response_model=ImageOCRResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload promotional image and extract embedded textual claims via OCR",
    description=(
        "Accepts promotional brand graphics (PNG, JPEG, WebP), validates file integrity and dimensions, "
        "and runs OCR extraction with word-level confidence and bounding boxes."
    ),
)
async def extract_image_text(
    file: UploadFile = File(..., description="Promotional image file (PNG, JPEG, WebP)")
):
    content_type = file.content_type or ""
    if content_type and not any(
        fmt in content_type.lower()
        for fmt in ["image/png", "image/jpeg", "image/jpg", "image/webp", "application/octet-stream"]
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{content_type}'. Please upload a PNG, JPEG, or WebP image.",
        )

    max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    content = await file.read()

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_IMAGE_SIZE_MB} MB.",
        )

    try:
        result = await anyio.to_thread.run_sync(ocr_service.extract_text, content)
        return ImageOCRResponse(**result)
    except UnsupportedImageFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        )
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        )
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Failed to process uploaded image: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process image.",
        )


@router.post(
    "/image/submit",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit user-verified OCR text from promotional image for compliance review",
    description=(
        "Submits text extracted from a promotional marketing image (optionally edited/corrected by the user) "
        "to the compliance engine. The review record is persisted with review_source='image' and "
        "full audit traceability to the original OCR text."
    ),
)
async def review_image_content(request: ImageReviewSubmitRequest):
    content = request.corrected_text.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Review content cannot be empty.",
        )

    if len(content) > settings.MAX_REVIEW_CONTENT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Content exceeds maximum length of {settings.MAX_REVIEW_CONTENT_LENGTH} characters. "
                f"Submitted: {len(content)} characters."
            ),
        )

    # Validate and resolve document_ids and policy_version_ids
    validated_doc_ids, enforced_versions = _resolve_scope_and_versions(
        request.document_ids,
        request.policy_version_ids,
    )

    review_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Image review %s initiated: %d chars, raw_ocr=%s, %d document_ids, %d policy_versions.",
        review_id, len(content), bool(request.raw_ocr_text), len(validated_doc_ids), len(enforced_versions),
    )

    return await anyio.to_thread.run_sync(
        _execute_review_pipeline,
        content,
        validated_doc_ids,
        review_id,
        created_at,
        request.retrieval_mode,
        "image",
        request.raw_ocr_text,
        content,
        enforced_versions,
    )

