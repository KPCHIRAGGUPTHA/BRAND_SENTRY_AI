"""
Document Text Extraction Service for BrandSentry AI.
Extracts clean, page-preserving text from PDF and TXT files with format validation.
"""
import io
import os
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


class DocumentExtractionError(Exception):
    """Base exception for extraction failures."""
    pass


class UnsupportedFormatError(DocumentExtractionError):
    """Raised when uploaded file format is unsupported."""
    pass


class EmptyDocumentError(DocumentExtractionError):
    """Raised when uploaded file contains zero bytes or zero text."""
    pass


class ScannedPDFError(DocumentExtractionError):
    """Raised when PDF contains no extractable digital text (e.g., scanned/image-only)."""
    pass


class CorruptedDocumentError(DocumentExtractionError):
    """Raised when file content is malformed or corrupted."""
    pass


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    char_count: int


@dataclass
class ExtractedDocument:
    filename: str
    file_type: str
    page_count: int
    total_characters: int
    pages: List[ExtractedPage]


class DocumentExtractor:
    """Handles format verification and text extraction for PDF and TXT guidelines."""

    @staticmethod
    def detect_and_validate_format(filename: str, content: bytes) -> str:
        """
        Validates content signatures and filename extensions.
        Returns 'pdf' or 'txt' if valid, else raises UnsupportedFormatError.
        """
        if not content or len(content) == 0:
            raise EmptyDocumentError("The uploaded file is empty (0 bytes).")

        lower_name = filename.lower()
        
        # Check PDF signature: magic bytes %PDF-
        if content.startswith(b"%PDF-"):
            if not lower_name.endswith(".pdf"):
                raise UnsupportedFormatError(
                    f"File content is PDF but filename '{filename}' does not end with .pdf"
                )
            return "pdf"

        # Check if named .pdf but doesn't have PDF magic bytes
        if lower_name.endswith(".pdf"):
            raise CorruptedDocumentError(
                f"File '{filename}' is named as a PDF but does not have valid PDF header signatures."
            )

        # Check TXT
        if lower_name.endswith(".txt"):
            # Verify it can be decoded as UTF-8 or UTF-8-sig
            try:
                content.decode("utf-8-sig")
                return "txt"
            except UnicodeDecodeError as exc:
                raise CorruptedDocumentError(
                    f"Text file '{filename}' could not be decoded as valid UTF-8: {str(exc)}"
                )

        raise UnsupportedFormatError(
            f"Unsupported file format for '{filename}'. BrandSentry AI accepts .pdf and .txt guidelines only."
        )

    @classmethod
    def extract_text(cls, filename: str, content: bytes) -> ExtractedDocument:
        """
        Extracts page-by-page text preserving metadata.
        """
        file_type = cls.detect_and_validate_format(filename, content)

        if file_type == "pdf":
            return cls._extract_pdf(filename, content)
        elif file_type == "txt":
            return cls._extract_txt(filename, content)
        else:
            raise UnsupportedFormatError(f"Unsupported format: {file_type}")

    @classmethod
    def _extract_pdf(cls, filename: str, content: bytes) -> ExtractedDocument:
        import fitz  # PyMuPDF

        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise CorruptedDocumentError(f"Failed to open PDF document '{filename}': {str(exc)}")

        try:
            page_count = len(doc)
            if page_count == 0:
                raise EmptyDocumentError(f"PDF document '{filename}' contains 0 pages.")

            extracted_pages: List[ExtractedPage] = []
            total_chars = 0

            for page_idx in range(page_count):
                page = doc[page_idx]
                page_text = page.get_text("text") or ""
                # Clean extraneous null bytes while preserving newlines & structure
                cleaned_text = page_text.replace("\x00", "").strip()
                char_count = len(cleaned_text)
                total_chars += char_count

                if cleaned_text:
                    extracted_pages.append(
                        ExtractedPage(
                            page_number=page_idx + 1,
                            text=cleaned_text,
                            char_count=char_count,
                        )
                    )

            if total_chars == 0:
                raise ScannedPDFError(
                    f"PDF document '{filename}' contains no extractable digital text. "
                    "Scanned documents requiring OCR are not supported in this phase."
                )

            return ExtractedDocument(
                filename=filename,
                file_type="pdf",
                page_count=page_count,
                total_characters=total_chars,
                pages=extracted_pages,
            )
        finally:
            doc.close()

    @classmethod
    def _extract_txt(cls, filename: str, content: bytes) -> ExtractedDocument:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CorruptedDocumentError(
                f"Failed to decode text file '{filename}' with UTF-8 encoding: {str(exc)}"
            )

        cleaned_text = text.replace("\x00", "").strip()
        if not cleaned_text:
            raise EmptyDocumentError(f"Text file '{filename}' contains only whitespace or no extractable characters.")

        # For plain text, preserve paragraph structures as page 1
        return ExtractedDocument(
            filename=filename,
            file_type="txt",
            page_count=1,
            total_characters=len(cleaned_text),
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=cleaned_text,
                    char_count=len(cleaned_text),
                )
            ],
        )
