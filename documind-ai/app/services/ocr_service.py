import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image

    _OCR_IMPORTS_AVAILABLE = True
except ImportError:
    _OCR_IMPORTS_AVAILABLE = False


def is_ocr_available() -> bool:
    """Check whether pytesseract, Pillow, and the Tesseract binary are available."""
    if not _OCR_IMPORTS_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_image_bytes(image_bytes: bytes) -> Optional[str]:
    """Run Tesseract OCR on raw image bytes. Returns None if OCR is unavailable or fails."""
    if not is_ocr_available():
        return None
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return None
