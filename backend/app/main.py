"""
BrandSentry AI — FastAPI Main Application Entry Point
"""
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.guidelines import router as guidelines_router
from backend.app.api.review import router as review_router
from backend.app.api.reviews import router as reviews_router
from backend.app.retrieval.embeddings import embedding_service

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


def _warm_embedding_model() -> None:
    try:
        embedding_service.generate_embeddings(["warm-up"])
    except Exception as exc:
        logger.warning("Embedding warm-up failed; it will load on first use: %s", exc)


@app.on_event("startup")
def warm_up_in_background() -> None:
    """Loads the model after a cold start so the first upload does not pay for it."""
    if settings.APP_ENV == "production":
        threading.Thread(target=_warm_embedding_model, daemon=True).start()


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint to verify backend service readiness."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
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
