"""
FastAPI Router for Guideline Ingestion and Retrieval.
Handles file uploads, text extraction, chunking, indexing, and semantic passage search.
"""
import hashlib
import os
import re
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from backend.app.core.config import settings
from backend.app.schemas.guideline import (
    GuidelineUploadResponse,
    GuidelineSearchRequest,
    GuidelineSearchResponse,
    GuidelineChunkMatch,
    DocumentListResponse,
    DocumentSummary,
)
from backend.app.services.document_registry import document_registry
from backend.app.services.extraction import (
    DocumentExtractor,
    DocumentExtractionError,
    UnsupportedFormatError,
    EmptyDocumentError,
    ScannedPDFError,
    CorruptedDocumentError,
)
from backend.app.services.chunking import document_chunker
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.vector_store import vector_store_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _sanitize_filename(name: str) -> str:
    """Strips path traversal components and unsafe characters from filenames."""
    basename = os.path.basename(name)
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", basename)
    return sanitized or "document"


@router.post(
    "/upload",
    response_model=GuidelineUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a brand guideline PDF or TXT file",
)
async def upload_guideline(file: UploadFile = File(...)):
    """
    Accepts PDF or TXT brand guideline files.
    Extracts text, splits into semantic chunks, generates embeddings, and persists in ChromaDB.
    Reuses existing records if identical file content was previously uploaded and indexed.
    """
    filename = file.filename or "unknown"
    sanitized_name = _sanitize_filename(filename)

    # Read content
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(exc)}",
        )

    # Size check
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # Empty check
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )

    # Stable content hash for duplicate detection
    content_hash = hashlib.sha256(content).hexdigest()

    # Safe deduplication: If this exact file content has already been successfully indexed,
    # reuse the existing document record without repeated vector indexing.
    existing_doc = document_registry.get_document_by_content_hash(content_hash)
    if existing_doc and existing_doc.get("status") == "indexed":
        logger.info(
            "Identical file content already indexed (%s: %s). Reusing existing record.",
            existing_doc["document_id"],
            existing_doc["filename"],
        )
        return GuidelineUploadResponse(
            document_id=existing_doc["document_id"],
            filename=sanitized_name,
            status="indexed",
            page_count=existing_doc.get("page_count"),
            extracted_characters=existing_doc.get("character_count", 0),
            chunk_count=existing_doc.get("chunk_count", 0),
            message="Document already indexed. Existing record reused.",
        )

    document_id = str(uuid.uuid4())
    stored_filename = f"{document_id}_{sanitized_name}"

    # Determine uploads directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uploads_dir = os.path.abspath(os.path.join(base_dir, "data", "uploads"))
    os.makedirs(uploads_dir, exist_ok=True)
    stored_path = os.path.join(uploads_dir, stored_filename)

    # 1. Format validation & text extraction
    try:
        extracted_doc = DocumentExtractor.extract_text(sanitized_name, content)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ScannedPDFError as exc:
        # 422 Unprocessable Entity for scanned PDFs needing OCR
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except CorruptedDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during text extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during text extraction: {str(exc)}",
        )

    # 2. Persist raw file securely
    try:
        with open(stored_path, "wb") as f:
            f.write(content)
    except Exception as exc:
        logger.error("Failed to write uploaded file to disk: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file on server.",
        )

    # 3. Register initial status in document registry
    document_registry.register_document(
        document_id=document_id,
        filename=sanitized_name,
        file_type=extracted_doc.file_type,
        file_size=len(content),
        stored_path=stored_path,
        status="processing",
        content_hash=content_hash,
    )

    # 4. Chunk document
    try:
        chunks = document_chunker.chunk_document(document_id, extracted_doc)
        if not chunks:
            raise EmptyDocumentError("No valid text chunks could be produced from document.")

        # 5. Generate embeddings
        chunk_texts = [c.text for c in chunks]
        embeddings = embedding_service.generate_embeddings(chunk_texts)

        # 6. Index into ChromaDB vector store
        vector_store_service.add_chunks(chunks, embeddings)

        # 7. Update status to indexed
        document_registry.update_status(
            document_id=document_id,
            status="indexed",
            page_count=extracted_doc.page_count,
            character_count=extracted_doc.total_characters,
            chunk_count=len(chunks),
        )

        return GuidelineUploadResponse(
            document_id=document_id,
            filename=sanitized_name,
            status="indexed",
            page_count=extracted_doc.page_count,
            extracted_characters=extracted_doc.total_characters,
            chunk_count=len(chunks),
            message="Document successfully processed, chunked, and indexed into vector store.",
        )

    except Exception as exc:
        logger.exception("Failed during indexing pipeline: %s", exc)
        document_registry.update_status(
            document_id=document_id,
            status="failed",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document indexing failed: {str(exc)}",
        )


@router.post(
    "/search",
    response_model=GuidelineSearchResponse,
    summary="Search for relevant guideline passages using natural-language compliance queries",
)
async def search_guidelines(request: GuidelineSearchRequest):
    """
    Retrieves top-k relevant guideline passages for a given natural-language query.
    Allows filtering by document_id.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty or whitespace.",
        )

    if len(query) > settings.MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Search query exceeds maximum length of {settings.MAX_QUERY_LENGTH} characters.",
        )

    # Validate document_id if provided
    if request.document_id:
        doc = document_registry.get_document(request.document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guideline document with ID '{request.document_id}' was not found.",
            )
        if doc["status"] != "indexed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{request.document_id}' is not indexed (status: {doc['status']}).",
            )

    top_k = min(request.top_k, settings.MAX_SEARCH_TOP_K)

    try:
        query_embedding = embedding_service.generate_query_embedding(query)
        matches = vector_store_service.search(
            query_embedding=query_embedding,
            document_id=request.document_id,
            top_k=top_k,
        )

        results = [
            GuidelineChunkMatch(
                chunk_id=m["chunk_id"],
                document_id=m["document_id"],
                source_filename=m["source_filename"],
                page_number=m["page_number"],
                chunk_index=m["chunk_index"],
                text=m["text"],
                distance=m["distance"],
                similarity_score=m["similarity_score"],
            )
            for m in matches
        ]

        return GuidelineSearchResponse(
            query=query,
            document_id=request.document_id,
            total_matches=len(results),
            results=results,
        )
    except Exception as exc:
        logger.exception("Search execution error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing semantic search: {str(exc)}",
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all registered guideline documents and their indexing statuses",
)
async def list_guidelines():
    """Returns metadata summaries for all uploaded guidelines."""
    docs = document_registry.list_documents()
    summaries = [
        DocumentSummary(
            document_id=d["document_id"],
            filename=d["filename"],
            status=d["status"],
            page_count=d["page_count"],
            character_count=d["character_count"],
            chunk_count=d["chunk_count"],
            created_at=d["created_at"],
            error_message=d.get("error_message"),
        )
        for d in docs
    ]
    return DocumentListResponse(total=len(summaries), documents=summaries)


@router.get(
    "/{document_id}",
    response_model=DocumentSummary,
    summary="Get status and details of a specific guideline document",
)
async def get_guideline(document_id: str):
    """Returns details and current status for a given document UUID."""
    doc = document_registry.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return DocumentSummary(
        document_id=doc["document_id"],
        filename=doc["filename"],
        status=doc["status"],
        page_count=doc["page_count"],
        character_count=doc["character_count"],
        chunk_count=doc["chunk_count"],
        created_at=doc["created_at"],
        error_message=doc.get("error_message"),
    )
