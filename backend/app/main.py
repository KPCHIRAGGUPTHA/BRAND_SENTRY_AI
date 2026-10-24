"""
BrandSentry AI — FastAPI Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.guidelines import router as guidelines_router
from backend.app.api.review import router as review_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BrandSentry AI — AI-powered brand compliance review platform.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Development CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(guidelines_router, prefix="/api/guidelines", tags=["Guidelines"])
app.include_router(review_router, prefix="/api/review", tags=["Review"])


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
