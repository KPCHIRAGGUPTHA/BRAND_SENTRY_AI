"""
Optical Character Recognition (OCR) Service for BrandSentry AI.
Extracts embedded textual claims from promotional marketing images (PNG, JPEG, WebP)
using Pillow and pytesseract with confidence scoring and bounding box traceability.
"""
import io
import os
import shutil
import logging
from typing import Dict, Any, List, Optional
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class UnsupportedImageFormatError(ValueError):
    """Raised when uploaded file is not a supported image format."""
    pass


class InvalidImageError(ValueError):
    """Raised when image bytes cannot be decoded or image is corrupted."""
    pass


class ImageTooLargeError(ValueError):
    """Raised when image exceeds dimension or file size limits."""
    pass


class OCRService:
    """
    Lightweight, robust OCR service for promotional brand images.
    """

    ALLOWED_FORMATS = {"PNG", "JPEG", "JPG", "WEBP"}
    MAX_DIMENSION = 8000
    MIN_DIMENSION = 10

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self._tesseract_cmd = tesseract_cmd or settings.TESSERACT_CMD
        self._init_tesseract_path()

    def _init_tesseract_path(self) -> None:
        """Configures pytesseract executable path across Linux, Docker, and Windows."""
        try:
            import pytesseract
        except ImportError:
            logger.warning("pytesseract library is not installed.")
            return

        candidate_paths = [
            self._tesseract_cmd,
            shutil.which("tesseract"),
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ]

        for path in candidate_paths:
            if path and os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info("Configured Tesseract binary at '%s'", path)
                return

        logger.info("Tesseract binary not found in standard system paths. pytesseract will rely on PATH lookup.")

    def is_tesseract_available(self) -> bool:
        """Checks if Tesseract binary is executable on this environment."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def validate_and_load_image(self, image_bytes: bytes) -> Image.Image:
        """
        Decodes image bytes, validates MIME format and dimensions.
        """
        if not image_bytes or len(image_bytes) == 0:
            raise InvalidImageError("Uploaded image file is empty (0 bytes).")

        max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
        if len(image_bytes) > max_bytes:
            raise ImageTooLargeError(
                f"Image file exceeds maximum allowed size of {settings.MAX_IMAGE_SIZE_MB} MB."
            )

        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
        except UnidentifiedImageError:
            raise UnsupportedImageFormatError(
                "Unsupported or unrecognized image format. Only PNG, JPEG, and WebP are supported."
            )
        except Exception as exc:
            raise InvalidImageError(f"Corrupted image data: {str(exc)}")

        # Re-open after verify() (Pillow requirement)
        img = Image.open(io.BytesIO(image_bytes))

        # Check format
        fmt = (img.format or "").upper()
        if fmt not in self.ALLOWED_FORMATS:
            raise UnsupportedImageFormatError(
                f"Unsupported format '{fmt}'. Allowed formats: {', '.join(sorted(self.ALLOWED_FORMATS))}."
            )

        width, height = img.size
        if width < self.MIN_DIMENSION or height < self.MIN_DIMENSION:
            raise InvalidImageError(
                f"Image dimensions ({width}x{height}) are too small. Minimum dimension is {self.MIN_DIMENSION}px."
            )
        if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
            raise ImageTooLargeError(
                f"Image dimensions ({width}x{height}) exceed maximum allowed dimension of {self.MAX_DIMENSION}px."
            )

        return img

    def extract_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Extracts structured text from promotional marketing image bytes.
        Returns:
            Dict containing:
            - status: 'success' | 'empty_text' | 'error'
            - extracted_text: str
            - confidence: float (0.0 to 100.0)
            - width: int
            - height: int
            - blocks: List of {text, confidence, bbox}
            - warning: Optional[str]
        """
        img = self.validate_and_load_image(image_bytes)
        width, height = img.size

        # Convert palette/transparency to RGB for OCR processing
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Check if tesseract binary is runnable
        if not self.is_tesseract_available():
            logger.warning("Tesseract engine not available for OCR. Prompting manual entry.")
            return {
                "status": "error",
                "extracted_text": "",
                "confidence": 0.0,
                "width": width,
                "height": height,
                "blocks": [],
                "warning": (
                    "Tesseract OCR executable is not available on this server environment. "
                    "Please enter or paste the marketing copy text manually."
                ),
            }

        import pytesseract

        try:
            # Preprocessing: convert to grayscale and apply autocontrast for sharp text edges
            gray_img = ImageOps.grayscale(img)
            enhanced_img = ImageOps.autocontrast(gray_img)

            # Extract detailed block and word data
            data = pytesseract.image_to_data(
                enhanced_img,
                output_type=pytesseract.Output.DICT,
            )

            blocks: List[Dict[str, Any]] = []
            extracted_words: List[str] = []
            confidences: List[float] = []

            n_boxes = len(data.get("text", []))
            for i in range(n_boxes):
                word = (data["text"][i] or "").strip()
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError):
                    conf = -1.0

                if word and conf >= 0:
                    extracted_words.append(word)
                    confidences.append(conf)
                    blocks.append({
                        "text": word,
                        "confidence": round(conf, 2),
                        "bbox": [
                            data["left"][i],
                            data["top"][i],
                            data["width"][i],
                            data["height"][i],
                        ],
                    })

            # Full text via image_to_string for optimal line breaking
            full_text = pytesseract.image_to_string(enhanced_img).strip()

            mean_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

            warning = None
            if not full_text:
                status = "empty_text"
                warning = "No extractable text detected in image. You may enter marketing claims manually."
            elif mean_confidence < 40.0:
                status = "success"
                warning = "Low OCR confidence detected. Please verify extracted claims before compliance review."
            else:
                status = "success"

            return {
                "status": status,
                "extracted_text": full_text,
                "confidence": mean_confidence,
                "width": width,
                "height": height,
                "blocks": blocks,
                "warning": warning,
            }

        except Exception as exc:
            logger.exception("OCR execution failed: %s", exc)
            return {
                "status": "error",
                "extracted_text": "",
                "confidence": 0.0,
                "width": width,
                "height": height,
                "blocks": [],
                "warning": f"OCR processing encountered an internal error: {str(exc)}",
            }


ocr_service = OCRService()
