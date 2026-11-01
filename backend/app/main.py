"""
BrandSentry AI — FastAPI Main Application Entry Point
"""
import logging
import os
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.guidelines import ingest_sample_guideline, router as guidelines_router
from backend.app.api.review import router as review_router
from backend.app.api.reviews import router as reviews_router
from backend.app.retrieval.embeddings import embedding_service
from backend.app.retrieval.vector_store import vector_store_service

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BrandSentry AI — AI-powered brand compliance review platform.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
cors_origins = settings.cors_origins
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(guidelines_router, prefix="/api/guidelines", tags=["Guidelines"])
app.include_router(review_router, prefix="/api/review", tags=["Review"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["Reviews Audit"])


_started_at = time.monotonic()
_readiness = {"state": "ready"}


def _prepare_backend() -> None:
    """Loads the model, then the sample guideline if nothing is indexed, so a restart is usable."""
    try:
        embedding_service.generate_embeddings(["warm-up"])
        if settings.AUTO_LOAD_SAMPLE_GUIDELINE and vector_store_service.count() == 0:
            ingest_sample_guideline()
    except Exception as exc:
        logger.warning("Backend warm-up failed; loading will happen on first use: %s", exc)
    finally:
        _readiness["state"] = "ready"


@app.on_event("startup")
def warm_up_in_background() -> None:
    """Runs in a thread so /health answers immediately during a cold start."""
    if settings.APP_ENV == "production":
        _readiness["state"] = "warming"
        threading.Thread(target=_prepare_backend, daemon=True).start()


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint to verify backend service readiness."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
        "readiness": _readiness["state"],
        "uptime_seconds": round(time.monotonic() - _started_at),
        "build": os.getenv("RENDER_GIT_COMMIT", "local")[:7],
    }


@app.get("/", tags=["System"])
async def root():
    """Root metadata endpoint."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs": "/docs",
    }
