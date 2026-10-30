"""
Application Configuration Module for BrandSentry AI.
Loads settings from environment variables or falls back to robust defaults.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")


class Settings(BaseSettings):
    PROJECT_NAME: str = Field(default="BrandSentry AI")
    VERSION: str = Field(default="0.3.0")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # Allowed CORS Origins
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    # Storage paths (configurable for persistent volume mounts)
    DATA_DIR: str = Field(default=_DEFAULT_DATA_DIR)
    UPLOADS_DIR: Optional[str] = Field(default=None)
    CHROMA_PERSIST_DIR: Optional[str] = Field(default=None)
    BM25_PERSIST_DIR: Optional[str] = Field(default=None)
    DOCUMENTS_DB_PATH: Optional[str] = Field(default=None)
    REVIEWS_DB_PATH: Optional[str] = Field(default=None)

    @property
    def uploads_dir(self) -> str:
        return self.UPLOADS_DIR or os.path.join(self.DATA_DIR, "uploads")

    @property
    def chroma_persist_dir(self) -> str:
        return self.CHROMA_PERSIST_DIR or os.path.join(self.DATA_DIR, "chroma")

    @property
    def bm25_persist_dir(self) -> str:
        return self.BM25_PERSIST_DIR or os.path.join(self.DATA_DIR, "bm25")

    @property
    def documents_db_path(self) -> str:
        return self.DOCUMENTS_DB_PATH or os.path.join(self.DATA_DIR, "documents.db")

    @property
    def reviews_db_path(self) -> str:
        return self.REVIEWS_DB_PATH or os.path.join(self.DATA_DIR, "reviews.db")

    # Ingestion constraints
    MAX_UPLOAD_SIZE_MB: int = Field(default=10)
    MAX_QUERY_LENGTH: int = Field(default=1000)
    MAX_SEARCH_TOP_K: int = Field(default=20)
    DEFAULT_SEARCH_TOP_K: int = Field(default=5)

    # Chunking configuration (approximating ~400 tokens / 50 tokens overlap)
    CHUNK_SIZE_WORDS: int = Field(default=300)
    CHUNK_OVERLAP_WORDS: int = Field(default=40)

    # Retrieval & Embedding settings (CPU-friendly, local)
    EMBEDDING_PROVIDER: str = Field(default="sentence-transformers")
    EMBEDDING_MODEL_NAME: str = Field(default="all-MiniLM-L6-v2")
    CHROMA_COLLECTION_NAME: str = Field(default="guideline_chunks")
    RETRIEVAL_MODE: str = Field(
        default="hybrid",
        description="Retrieval engine mode: 'hybrid' (Dense + BM25 + RRF), 'hybrid_rerank' (Dense + BM25 + RRF + Cross-Encoder), 'dense', or 'bm25'",
    )
    RRF_SMOOTHING_K: int = Field(
        default=60,
        description="Reciprocal Rank Fusion smoothing constant k (default: 60)",
    )
    RERANKING_ENABLED: bool = Field(
        default=True,
        description="Whether Cross-Encoder reranking is enabled",
    )
    RERANKER_MODEL_NAME: str = Field(
        default="Xenova/ms-marco-MiniLM-L-6-v2",
        description="Cross-Encoder model for claim-passage contextual reranking",
    )
    RERANKER_CANDIDATE_POOL: int = Field(
        default=15,
        description="Number of candidate passages to retrieve before cross-encoder reranking",
    )
    RERANKER_MAX_LENGTH: int = Field(
        default=256,
        description="Max token sequence length for cross-encoder query-passage input",
    )

    # Multimodal & Visual Brand Compliance (Improvement 3)
    MAX_IMAGE_SIZE_MB: int = Field(default=10, description="Maximum image upload size in MB")
    TESSERACT_CMD: Optional[str] = Field(
        default=None,
        description="Explicit path to tesseract binary if not in PATH",
    )

    # Phase 3 — Review & Verdict Engine
    MAX_REVIEW_CONTENT_LENGTH: int = Field(
        default=5000,
        description="Maximum characters in a marketing content review request.",
    )
    REVIEW_EVIDENCE_TOP_K: int = Field(
        default=4,
        description="Number of guideline passages retrieved per claim for verdict grounding.",
    )
    # WARNING: This threshold is approximate and NOT a calibrated confidence measure.
    # A passage above this threshold is only a candidate for verdict consideration,
    # not proof of support or contradiction. Document this limitation when surfacing it.
    VERDICT_SIMILARITY_THRESHOLD: float = Field(
        default=0.25,
        description=(
            "Approximate cosine-similarity floor for evidence candidates (0–1). "
            "NOT a calibrated confidence or probability. Adjust based on empirical evaluation."
        ),
    )

    # LLM Settings (Provider-Independent Interface for Phase 3)
    LLM_PROVIDER: str = Field(default="gemini")
    LLM_MODEL: str = Field(default="gemini-1.5-flash")
    LLM_API_KEY: str = Field(default="")
    LLM_TEMPERATURE: float = Field(default=0.1)
    LLM_MAX_OUTPUT_TOKENS: int = Field(default=2048)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        """True only when a real API key is present (not the placeholder)."""
        return bool(self.LLM_API_KEY and self.LLM_API_KEY != "YOUR_API_KEY_HERE")


settings = Settings()
