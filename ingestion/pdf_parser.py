from __future__ import annotations

from dataclasses import dataclass

import pdfplumber

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


@dataclass
class PdfExtractionResult:
    text: str
    needs_ocr: bool           # True if neither library found real text
    used_fallback: bool       # True if PyMuPDF was needed


_MIN_CHARS_PER_PAGE_TO_TRUST = 20  # below this, assume it's a scan, not native text


def extract_native_pdf_text(filepath: str) -> PdfExtractionResult:
    text_chunks: list[str] = []
    any_page_has_content_but_no_text = False

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            has_images_or_boxes = bool(page.images) or bool(page.rects)

            if len(page_text.strip()) < _MIN_CHARS_PER_PAGE_TO_TRUST:
                if has_images_or_boxes:
                    any_page_has_content_but_no_text = True
                # still keep whatever tiny bit of text there was
            text_chunks.append(page_text)

    combined = "\n".join(text_chunks).strip()

    if len(combined) >= _MIN_CHARS_PER_PAGE_TO_TRUST:
        return PdfExtractionResult(text=combined, needs_ocr=False, used_fallback=False)

    # pdfplumber found ~nothing — try PyMuPDF before concluding it's a scan
    if fitz is not None:
        fallback_text = _extract_with_pymupdf(filepath)
        if len(fallback_text.strip()) >= _MIN_CHARS_PER_PAGE_TO_TRUST:
            return PdfExtractionResult(text=fallback_text, needs_ocr=False, used_fallback=True)

    # Both libraries found nothing real -> this is a scanned/photographed PDF
    return PdfExtractionResult(text=combined, needs_ocr=True, used_fallback=False)


def _extract_with_pymupdf(filepath: str) -> str:
    doc = fitz.open(filepath)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def render_pdf_pages_as_images(filepath: str, dpi: int = 300):
    """Used by ocr.py when needs_ocr=True. Kept here (not in ocr.py) so
    ocr.py doesn't need to know anything about PDFs specifically — it
    only ever receives a list of PIL images, whether they came from a
    PDF or were a standalone photo to begin with."""
    from pdf2image import convert_from_path
    return convert_from_path(filepath, dpi=dpi)
