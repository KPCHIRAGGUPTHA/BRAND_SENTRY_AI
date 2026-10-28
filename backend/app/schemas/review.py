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
    retrieval_mode: Optional[str] = Field(
        default=None,
        description="Optional retrieval mode override ('hybrid', 'dense', or 'bm25'). Defaults to server configuration.",
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
    bm25_score: Optional[float] = Field(
        default=None,
        description="BM25 score if retrieved via lexical search",
    )
    rrf_score: Optional[float] = Field(
        default=None,
        description="Reciprocal Rank Fusion score if retrieved via hybrid search",
    )



class SemanticDriftIssue(BaseModel):
    """A detected semantic drift issue between claim and evidence."""
    category: str = Field(description="Drift category (e.g. CERTAINTY_SHIFT, SCOPE_EXPANSION, NUMERICAL_EXAGGERATION).")
    severity: str = Field(description="Severity of the drift: 'LOW' | 'MEDIUM' | 'HIGH'.")
    claim_phrase: str = Field(description="Relevant phrase in the submitted marketing claim.")
    source_phrase: str = Field(description="Corresponding factual or policy statement in the retrieved evidence.")
    explanation: str = Field(description="Human-readable explanation of why this constitutes semantic drift.")
    suggested_correction: Optional[str] = Field(
        default=None,
        description="Suggested adjustment to realign the claim with the evidence.",
    )


class SemanticDriftResult(BaseModel):
    """Analysis of semantic drift for a marketing claim."""
    detected: bool = Field(description="True if one or more semantic drift issues were identified.")
    issues: List[SemanticDriftIssue] = Field(
        default_factory=list,
        description="List of detected drift issues.",
    )
    uncertainty: Optional[str] = Field(
        default=None,
        description="Explanation if evidence was insufficient or lacking topic overlap to evaluate drift.",
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
    semantic_drift: Optional[SemanticDriftResult] = Field(
        default=None,
        description="Detailed analysis of semantic drift between claim and retrieved evidence.",
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
    review_source: str = Field(
        default="text",
        description="Origin of reviewed content: 'text' or 'image'",
    )
    ocr_raw_text: Optional[str] = Field(
        default=None,
        description="Raw text extracted by OCR if source was image",
    )
    ocr_user_text: Optional[str] = Field(
        default=None,
        description="User-corrected text before compliance review",
    )


class OCRTextBlock(BaseModel):
    text: str
    confidence: float
    bbox: Optional[List[int]] = Field(default=None, description="[x, y, width, height]")


class ImageOCRResponse(BaseModel):
    """Response returned upon uploading promotional image for OCR extraction."""
    status: str = Field(description="'success', 'empty_text', or 'error'")
    extracted_text: str = Field(description="Full concatenated text extracted from image")
    confidence: float = Field(description="Mean OCR confidence percentage [0.0 - 100.0]")
    width: int
    height: int
    blocks: List[OCRTextBlock] = Field(default_factory=list)
    warning: Optional[str] = None


class ImageReviewSubmitRequest(BaseModel):
    """Request to review user-verified OCR text through compliance engine."""
    corrected_text: str = Field(
        ...,
        min_length=1,
        description="User-reviewed marketing text extracted from the promotional image",
    )
    raw_ocr_text: Optional[str] = Field(
        default=None,
        description="Original uncorrected OCR text for audit traceability",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of guideline document UUIDs to scope evidence retrieval",
    )
    retrieval_mode: Optional[str] = Field(
        default=None,
        description="Optional retrieval mode override ('hybrid', 'dense', or 'bm25')",
    )

    @field_validator("corrected_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Corrected promotional text cannot be empty or whitespace.")
        return v
