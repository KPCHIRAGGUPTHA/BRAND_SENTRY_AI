"""
Integration Tests for Guideline Ingestion and Retrieval API
"""
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_upload_valid_txt_file():
    """Verify successful upload, chunking, and indexing of TXT guideline."""
    txt_content = (
        "Brand Compliance Policy 2026\n"
        "Section 1: Logo Usage\n"
        "The corporate logo must always appear on pure white or midnight slate backgrounds.\n"
        "Section 2: Comparative Claims\n"
        "All comparative claims against competitors require third-party laboratory verification."
    ).encode("utf-8")

    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("brand_policy.txt", io.BytesIO(txt_content), "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "brand_policy.txt"
    assert data["status"] == "indexed"
    assert data["extracted_characters"] > 0
    assert data["chunk_count"] > 0


def test_upload_valid_pdf_file():
    """Verify successful upload, text extraction, and indexing of PDF guideline."""
    import fitz

    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Brand Safety Manual: Prohibited Words. Never use '100% Guaranteed'.")
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("brand_safety.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "brand_safety.pdf"
    assert data["page_count"] == 1
    assert data["chunk_count"] >= 1
    assert data["status"] == "indexed"


def test_upload_empty_file_rejected():
    """Verify that uploading an empty file returns HTTP 400."""
    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_unsupported_format_rejected():
    """Verify that unsupported extensions return HTTP 400."""
    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("rules.docx", io.BytesIO(b"fake docx binary data"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()


def test_upload_corrupted_pdf_rejected():
    """Verify that a corrupted PDF header returns HTTP 400."""
    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"Not a PDF header at all"), "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_scanned_pdf_without_text_rejected():
    """Verify that a PDF with zero extractable text returns HTTP 422."""
    import fitz

    doc = fitz.open()
    doc.new_page()  # blank page
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("scanned.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 422
    assert "scanned" in response.json()["detail"].lower()


def test_search_guidelines_retrieval():
    """Verify semantic search returns relevant passages and metadata."""
    # Upload sample guideline first
    sample_text = (
        "Official Packaging Guidelines:\n"
        "Always include mandatory recycling symbols on secondary packaging.\n"
        "Never use unapproved fluorescent green ink on the primary logo."
    ).encode("utf-8")

    upload_res = client.post(
        "/api/guidelines/upload",
        files={"file": ("packaging.txt", io.BytesIO(sample_text), "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]

    # Search for recycling symbols
    search_res = client.post(
        "/api/guidelines/search",
        json={"query": "recycling symbols on packaging", "document_id": doc_id, "top_k": 3},
    )

    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_matches"] > 0
    top_match = search_data["results"][0]
    assert "recycling symbols" in top_match["text"].lower()
    assert top_match["document_id"] == doc_id
    assert "distance" in top_match
    assert "similarity_score" in top_match


def test_search_unknown_document_id():
    """Verify search with non-existent document ID returns HTTP 404."""
    response = client.post(
        "/api/guidelines/search",
        json={"query": "random query", "document_id": "non-existent-uuid-12345"},
    )
    assert response.status_code == 404


def test_search_empty_query_rejected():
    """Verify search with empty query returns HTTP 400 or 422."""
    response = client.post(
        "/api/guidelines/search",
        json={"query": "   ", "top_k": 5},
    )
    assert response.status_code in (400, 422)


def test_list_and_get_guidelines():
    """Verify listing and retrieving document metadata."""
    list_res = client.get("/api/guidelines")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert "total" in list_data
    assert "documents" in list_data
    assert list_data["total"] > 0

    first_doc_id = list_data["documents"][0]["document_id"]
    get_res = client.get(f"/api/guidelines/{first_doc_id}")
    assert get_res.status_code == 200
    doc_detail = get_res.json()
    assert doc_detail["document_id"] == first_doc_id
    assert doc_detail["status"] == "indexed"
