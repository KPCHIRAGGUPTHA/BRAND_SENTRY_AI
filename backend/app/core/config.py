"""
Application Configuration Module for BrandSentry AI.
Loads settings from environment variables or falls back to robust defaults.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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

    # Storage paths
    DATA_DIR: str = Field(default="../data")
    UPLOADS_DIR: str = Field(default="../data/uploads")
    CHROMA_PERSIST_DIR: str = Field(default="../data/chroma")
    DOCUMENTS_DB_PATH: str = Field(default="../data/documents.db")
    REVIEWS_DB_PATH: str = Field(default="../data/reviews.db")

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
