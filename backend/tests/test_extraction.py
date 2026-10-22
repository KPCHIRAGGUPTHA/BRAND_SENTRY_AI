"""
Unit Tests for Document Text Extraction Service
"""
import io
import pytest
from backend.app.services.extraction import (
    DocumentExtractor,
    UnsupportedFormatError,
    EmptyDocumentError,
    CorruptedDocumentError,
    ScannedPDFError,
)


def test_txt_extraction_valid_utf8():
    """Verify clean extraction from standard UTF-8 text file."""
    content = "Brand Rule 1: Always use the official indigo logo.\nBrand Rule 2: No false claims.".encode("utf-8")
    doc = DocumentExtractor.extract_text("guidelines.txt", content)

    assert doc.filename == "guidelines.txt"
    assert doc.file_type == "txt"
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].page_number == 1
    assert "Always use the official indigo logo" in doc.pages[0].text
    assert doc.total_characters > 0


def test_txt_extraction_utf8_bom():
    """Verify that text files with UTF-8 BOM are handled without corruption."""
    content = "Brand Rule: Disclaimers required on discounts.".encode("utf-8-sig")
    doc = DocumentExtractor.extract_text("rules_bom.txt", content)

    assert doc.file_type == "txt"
    assert doc.pages[0].text.startswith("Brand Rule:")


def test_empty_file_raises_error():
    """Verify that a 0-byte file raises EmptyDocumentError."""
    with pytest.raises(EmptyDocumentError):
        DocumentExtractor.extract_text("empty.txt", b"")

    with pytest.raises(EmptyDocumentError):
        DocumentExtractor.extract_text("empty.pdf", b"")


def test_whitespace_only_txt_raises_error():
    """Verify that a text file containing only whitespace raises EmptyDocumentError."""
    with pytest.raises(EmptyDocumentError):
        DocumentExtractor.extract_text("blank.txt", b"   \n\n\t  ")


def test_unsupported_extension_raises_error():
    """Verify that non-supported file formats raise UnsupportedFormatError."""
    with pytest.raises(UnsupportedFormatError):
        DocumentExtractor.extract_text("presentation.pptx", b"dummy presentation data")

    with pytest.raises(UnsupportedFormatError):
        DocumentExtractor.extract_text("executable.exe", b"MZ\x90\x00\x03\x00\x00\x00")


def test_corrupted_pdf_signature_raises_error():
    """Verify that a file named .pdf but lacking %PDF- header raises CorruptedDocumentError."""
    fake_pdf = b"This is just plain text, not a PDF header."
    with pytest.raises(CorruptedDocumentError):
        DocumentExtractor.extract_text("corrupted.pdf", fake_pdf)


def test_pdf_extraction_with_pymupdf():
    """Verify that valid synthetic PDF can be created, extracted, and page numbers preserved."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not yet installed in runtime.")

    # Create an in-memory 2-page PDF
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Brand Policy Page 1: Do not use unapproved taglines.")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Brand Policy Page 2: Trademark symbol required.")

    pdf_bytes = doc.tobytes()
    doc.close()

    extracted = DocumentExtractor.extract_text("brand_policy.pdf", pdf_bytes)
    assert extracted.file_type == "pdf"
    assert extracted.page_count == 2
    assert len(extracted.pages) == 2
    assert extracted.pages[0].page_number == 1
    assert "Do not use unapproved taglines" in extracted.pages[0].text
    assert extracted.pages[1].page_number == 2
    assert "Trademark symbol required" in extracted.pages[1].text


def test_scanned_pdf_without_text_raises_scanned_pdf_error():
    """Verify that a PDF containing blank pages with 0 digital text raises ScannedPDFError."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not yet installed in runtime.")

    # Create a 1-page blank PDF (simulating scanned document with no text layer)
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(ScannedPDFError):
        DocumentExtractor.extract_text("scanned_image.pdf", pdf_bytes)
