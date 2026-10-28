"""
Tests for Improvement 3: Multimodal Visual Brand Compliance (OCR & Image Review).
Covers image validation, error handling, structured OCR extraction,
corrected text workflow, and end-to-end audit persistence.
"""
import io
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.ocr_service import (
    ocr_service,
    UnsupportedImageFormatError,
    InvalidImageError,
    ImageTooLargeError,
)
from backend.app.services.audit_service import audit_service


def _create_synthetic_image(
    format: str = "PNG",
    size: tuple = (300, 100),
    color: tuple = (255, 255, 255),
    text: str = "",
) -> bytes:
    """Helper to generate in-memory synthetic image bytes."""
    img = Image.new("RGB", size, color=color)
    if text:
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def client():
    return TestClient(app)


def test_ocr_validate_valid_png():
    img_bytes = _create_synthetic_image("PNG", size=(200, 100))
    img = ocr_service.validate_and_load_image(img_bytes)
    assert img.size == (200, 100)
    assert img.format == "PNG"


def test_ocr_validate_valid_jpeg():
    img_bytes = _create_synthetic_image("JPEG", size=(250, 120))
    img = ocr_service.validate_and_load_image(img_bytes)
    assert img.size == (250, 120)
    assert img.format == "JPEG"


def test_ocr_validate_empty_bytes():
    with pytest.raises(InvalidImageError, match="empty"):
        ocr_service.validate_and_load_image(b"")


def test_ocr_validate_corrupted_bytes():
    with pytest.raises(InvalidImageError, match="Corrupted"):
        ocr_service.validate_and_load_image(b"\x89PNG\r\n\x1a\nNotAValidPngStreamData")


def test_ocr_validate_unsupported_format():
    # BMP format
    img_bytes = _create_synthetic_image("BMP", size=(100, 100))
    with pytest.raises(UnsupportedImageFormatError, match="Unsupported format"):
        ocr_service.validate_and_load_image(img_bytes)


def test_ocr_validate_too_small():
    img_bytes = _create_synthetic_image("PNG", size=(5, 5))
    with pytest.raises(InvalidImageError, match="too small"):
        ocr_service.validate_and_load_image(img_bytes)


def test_ocr_validate_too_large_dimension():
    # Dimension limit is 8000
    img_bytes = _create_synthetic_image("PNG", size=(8001, 20))
    with pytest.raises(ImageTooLargeError, match="exceed maximum allowed dimension"):
        ocr_service.validate_and_load_image(img_bytes)


def test_ocr_extract_text_empty_image():
    # Image with pure white background, no text
    img_bytes = _create_synthetic_image("PNG", size=(300, 100), color=(255, 255, 255))
    res = ocr_service.extract_text(img_bytes)
    assert res["status"] in ("empty_text", "error")
    assert res["width"] == 300
    assert res["height"] == 100


def test_api_upload_image_endpoint(client):
    img_bytes = _create_synthetic_image("PNG", size=(300, 100), text="Sample Ad Copy")
    response = client.post(
        "/api/review/image",
        files={"file": ("promo.png", img_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "extracted_text" in data
    assert data["width"] == 300
    assert data["height"] == 100


def test_api_upload_unsupported_media_type(client):
    response = client.post(
        "/api/review/image",
        files={"file": ("doc.pdf", b"%PDF-1.4...", "application/pdf")},
    )
    assert response.status_code == 415
    assert "Unsupported media type" in response.json()["detail"]


def test_api_upload_corrupted_image(client):
    response = client.post(
        "/api/review/image",
        files={"file": ("corrupt.png", b"\x89PNG\r\n\x1a\nBADPNGDATA", "image/png")},
    )
    assert response.status_code == 400
    assert "Corrupted" in response.json()["detail"]


def test_api_image_review_submit_pipeline(client):
    # Submit user-verified OCR text from promo image
    payload = {
        "corrected_text": "Our product is guaranteed 100% risk-free with zero side effects.",
        "raw_ocr_text": "0ur pr0duct is guarantee 100% risk free",
        "retrieval_mode": "hybrid",
    }
    response = client.post("/api/review/image/submit", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["review_source"] == "image"
    assert data["ocr_raw_text"] == "0ur pr0duct is guarantee 100% risk free"
    assert data["ocr_user_text"] == payload["corrected_text"]
    assert len(data["claims"]) >= 1

    review_id = data["review_id"]

    # Verify audit persistence recorded source as 'image'
    audit_rec = audit_service.get_review(review_id)
    assert audit_rec is not None
    assert audit_rec["review_source"] == "image"
    assert audit_rec["ocr_raw_text"] == "0ur pr0duct is guarantee 100% risk free"
    assert audit_rec["ocr_corrected_text"] == payload["corrected_text"]


def test_api_image_review_submit_empty(client):
    payload = {
        "corrected_text": "   ",
        "raw_ocr_text": "",
    }
    response = client.post("/api/review/image/submit", json=payload)
    assert response.status_code in (400, 422)
