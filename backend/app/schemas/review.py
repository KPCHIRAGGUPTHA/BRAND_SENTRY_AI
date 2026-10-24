"""
Pydantic Schemas for Phase 3 — Marketing Content Review & Compliance Verdicts.
"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class ReviewRequest(BaseModel):
    """Request to submit marketing content for compliance review."""
    content: str = Field(
        ...,
        min_length=1,
        description="Marketing text to be reviewed for brand compliance.",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional list of guideline document UUIDs to scope the evidence search. "
            "If omitted or empty, all indexed guidelines are searched."
        ),
    )

    @field_validator("content")
    @classmethod
    def content_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Marketing content cannot be empty or whitespace-only.")
        return v


class EvidenceItemSchema(BaseModel):
    """A single guideline passage cited as evidence for a verdict."""
    chunk_id: str = Field(description="Unique chunk identifier from ChromaDB.")
    document_id: str = Field(description="UUID of the source guideline document.")
    source_filename: str = Field(description="Original filename of the guideline.")
    page_number: Optional[int] = Field(
        default=None,
        description="Page number within the source document (1-indexed, if available).",
    )
    quote: str = Field(
        description=(
            "Validated excerpt from the retrieved passage. "
            "This text is a confirmed substring of the actual stored passage — it is NOT fabricated."
        )
    )
    similarity_score: float = Field(
        description=(
            "Cosine similarity between the claim embedding and this passage embedding. "
            "Range [0.0, 1.0]. Used for ranking only — NOT a compliance confidence or probability."
        )
    )
    distance: float = Field(
        description="ChromaDB cosine distance (1 - similarity_score). Range [0.0, 1.0]."
    )


class ClaimVerdictSchema(BaseModel):
    """Compliance verdict for a single extracted marketing claim."""
    claim_id: str = Field(description="Stable identifier: 'claim-1', 'claim-2', etc.")
    claim_text: str = Field(description="Original claim text as extracted from marketing content.")
    verdict: str = Field(
        description=(
            "Three-way compliance verdict: "
            "'SUPPORTED' | 'CONTRADICTED' | 'INSUFFICIENT_EVIDENCE'. "
            "SUPPORTED: evidence affirmatively supports the claim. "
            "CONTRADICTED: evidence or a deterministic rule conflicts with the claim. "
            "INSUFFICIENT_EVIDENCE: available guidelines cannot determine compliance."
        )
    )
    explanation: str = Field(
        description="Factual explanation of the verdict, citing specific guideline passages where applicable."
    )
    evidence: List[EvidenceItemSchema] = Field(
        default_factory=list,
        description="Guideline passages used to reach the verdict. May be empty for deterministic-rule verdicts.",
    )
    suggested_correction: Optional[str] = Field(
        default=None,
        description=(
            "Conservative draft revision for contradicted or inconclusive claims. "
            "This is a draft for human review — it does NOT guarantee legal compliance."
        ),
    )
    deterministic_rule_fired: bool = Field(
        default=False,
        description="True when the verdict was determined by an explicit prohibited-phrase rule, not by retrieval.",
    )


class ReviewSummary(BaseModel):
    """Aggregate counts across all claim verdicts in a review."""
    total_claims: int
    supported: int
    contradicted: int
    insufficient_evidence: int


class ReviewResponse(BaseModel):
    """Complete compliance review result for a marketing content submission."""
    review_id: str = Field(description="Unique UUID for this review session.")
    content_preview: str = Field(
        description="First 120 characters of the submitted content (for UI display)."
    )
    document_ids_searched: List[str] = Field(
        description="Document UUIDs that were searched. Empty list means all guidelines were searched."
    )
    claims: List[ClaimVerdictSchema] = Field(
        description="Per-claim verdict objects in extraction order."
    )
    summary: ReviewSummary = Field(
        description="Aggregate counts across all verdicts."
    )
    created_at: str = Field(description="ISO 8601 timestamp of review creation (UTC).")
    warning: Optional[str] = Field(
        default=None,
        description="Non-fatal warning, e.g. 'No guidelines indexed — evidence not available.'",
    )
