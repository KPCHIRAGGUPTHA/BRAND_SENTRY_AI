"""
Pydantic Schemas for Guideline Ingestion and Retrieval
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class GuidelineUploadResponse(BaseModel):
    document_id: str = Field(description="Unique UUID identifying the uploaded document")
    filename: str = Field(description="Original filename uploaded by the user")
    status: str = Field(description="Processing status: 'indexed', 'processing', or 'failed'")
    page_count: Optional[int] = Field(default=None, description="Total number of pages if applicable")
    extracted_characters: int = Field(description="Total count of extractable text characters")
    chunk_count: int = Field(description="Total number of searchable chunks generated")
    message: Optional[str] = Field(default=None, description="Status or error message")


class GuidelineSearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language compliance query or claim to search for in guidelines",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Optional document UUID filter. If omitted, searches across all indexed guidelines.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of relevant guideline passages to return (1-20)",
    )


class GuidelineChunkMatch(BaseModel):
    chunk_id: str = Field(description="Unique chunk identifier")
    document_id: str = Field(description="UUID of source guideline document")
    source_filename: str = Field(description="Original filename of the guideline document")
    page_number: Optional[int] = Field(default=None, description="Page number where chunk appears (1-indexed)")
    chunk_index: int = Field(description="Zero-based sequence index of the chunk in document")
    text: str = Field(description="Original extracted text passage for verifiable citation")
    distance: float = Field(
        description="Vector distance score (lower represents closer semantic proximity). Note: this is a vector metric, not a calibrated probability."
    )
    similarity_score: float = Field(
        description="Normalized similarity metric (1.0 - normalized distance). Intended for ranking comparison only."
    )


class GuidelineSearchResponse(BaseModel):
    query: str
    document_id: Optional[str] = None
    total_matches: int
    results: List[GuidelineChunkMatch]


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: Optional[int] = None
    character_count: int
    chunk_count: int
    created_at: str
    error_message: Optional[str] = None


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentSummary]
