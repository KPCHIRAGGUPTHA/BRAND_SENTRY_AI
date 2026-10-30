"""
FastAPI Router for Review Audit History and Multi-Format Exports.
Provides endpoints for browsing historical reviews, dashboard statistics,
and exporting immutable reports in JSON, CSV, and PDF formats.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, Response

from backend.app.services.audit_service import audit_service

router = APIRouter()


@router.get(
    "",
    summary="List historical compliance reviews with pagination and summary counts",
)
async def list_reviews(
    limit: int = Query(default=20, ge=1, le=100, description="Max reviews to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    source: Optional[str] = Query(default=None, description="Filter by review source: 'text' or 'image'"),
):
    """Returns paginated review audit records."""
    return audit_service.list_reviews(limit=limit, offset=offset, source=source)


@router.get(
    "/stats/summary",
    summary="Get aggregate compliance analytics and metrics for dashboard",
)
async def get_review_stats():
    """Returns real aggregate review metrics, verdict counts, and guideline statistics."""
    return audit_service.get_dashboard_stats()


@router.get(
    "/{review_id}",
    summary="Retrieve full details and claim-level evidence for a saved review",
)
async def get_review(review_id: str):
    """Returns complete audit record for a given review UUID."""
    review = audit_service.get_review(review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review audit record with ID '{review_id}' was not found.",
        )
    return review


@router.get(
    "/{review_id}/export",
    summary="Export review audit report in JSON, CSV, or PDF format",
)
async def export_review(
    review_id: str,
    format: str = Query(default="json", pattern="^(json|csv|pdf)$", description="Export format: json, csv, or pdf"),
):
    """
    Exports saved audit record as a downloadable file.
    Does NOT re-run AI inference or retrieval.
    """
    review = audit_service.get_review(review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review with ID '{review_id}' was not found.",
        )

    clean_format = format.lower()
    filename_base = f"BrandSentry_Audit_{review_id[:8]}"

    if clean_format == "json":
        return JSONResponse(
            content=review,
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}.json"',
            },
        )
    elif clean_format == "csv":
        csv_data = audit_service.export_csv(review_id)
        if not csv_data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to format CSV export.")
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}.csv"',
            },
        )
    elif clean_format == "pdf":
        try:
            pdf_bytes = audit_service.export_pdf(review_id)
            if not pdf_bytes:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate PDF export.")
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename_base}.pdf"',
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating PDF report: {str(exc)}",
            )
