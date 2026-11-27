import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF
from app.services.ocr_service import is_ocr_available, ocr_image_bytes

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH_PER_PAGE = 20


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    used_ocr: bool = False


@dataclass
class ExtractionResult:
    success: bool
    pages: List[ExtractedPage]
    extraction_status: str  # 'completed' | 'ocr_completed' | 'insufficient_text' | 'failed'
    error_message: Optional[str] = None


def extract_text_from_pdf(pdf_path: Path) -> ExtractionResult:
    """
    Extract text page-by-page from a PDF using PyMuPDF.
    Falls back to Tesseract OCR only if text is insufficient and OCR is available.
    """
    if not pdf_path.exists():
        return ExtractionResult(
            success=False,
            pages=[],
            extraction_status="failed",
            error_message="PDF file not found on disk.",
        )

    pages: List[ExtractedPage] = []
    ocr_used_any = False

    try:
        with fitz.open(pdf_path) as doc:
            if doc.page_count == 0:
                return ExtractionResult(
                    success=False,
                    pages=[],
                    extraction_status="failed",
                    error_message="PDF contains zero pages.",
                )

            for idx, page in enumerate(doc, start=1):
                text = (page.get_text("text") or "").strip()
                used_ocr = False

                if len(text) < MIN_TEXT_LENGTH_PER_PAGE:
                    if is_ocr_available():
                        pix = page.get_pixmap(dpi=200)
                        ocr_text = ocr_image_bytes(pix.tobytes("png"))
                        if ocr_text:
                            text = ocr_text
                            used_ocr = True
                            ocr_used_any = True

                pages.append(
                    ExtractedPage(page_number=idx, text=text, used_ocr=used_ocr)
                )

        total_chars = sum(len(p.text) for p in pages)
        if total_chars < MIN_TEXT_LENGTH_PER_PAGE:
            ocr_note = (
                "OCR was attempted but yielded insufficient text."
                if is_ocr_available()
                else "Tesseract OCR is not installed; scanned PDFs cannot be OCR'd."
            )
            return ExtractionResult(
                success=False,
                pages=pages,
                extraction_status="insufficient_text",
                error_message=f"Insufficient extractable text. {ocr_note}",
            )

        status = "ocr_completed" if ocr_used_any else "completed"
        return ExtractionResult(
            success=True,
            pages=pages,
            extraction_status=status,
        )
    except Exception as exc:
        logger.exception("PDF extraction failed for %s", pdf_path.name)
        return ExtractionResult(
            success=False,
            pages=[],
            extraction_status="failed",
            error_message=f"PDF extraction error: {exc}",
        )
