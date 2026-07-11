from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image


@dataclass
class OcrResult:
    text: str
    mean_confidence: float   # 0-100, from Tesseract's own per-word confidence
    low_confidence: bool     # convenience flag: True biases toward needs_review downstream


_LOW_CONFIDENCE_THRESHOLD = 60.0


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Grayscale + adaptive threshold. This single step fixes most of
    Tesseract's accuracy problems on phone photos (uneven lighting,
    slight blur, background noise)."""
    img = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return Image.fromarray(thresh)


def ocr_image(image: Image.Image) -> OcrResult:
    processed = preprocess_for_ocr(image)

    data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
    words = [w for w in data["text"] if w.strip()]
    confidences = [float(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and c != "-1"]

    text = " ".join(words)
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return OcrResult(
        text=text,
        mean_confidence=mean_conf,
        low_confidence=mean_conf < _LOW_CONFIDENCE_THRESHOLD,
    )


def ocr_pdf_pages(images: list[Image.Image]) -> OcrResult:
    """Runs ocr_image across all pages of a scanned PDF and combines them."""
    page_results = [ocr_image(img) for img in images]
    combined_text = "\n".join(r.text for r in page_results)
    avg_conf = (
        sum(r.mean_confidence for r in page_results) / len(page_results)
        if page_results else 0.0
    )
    return OcrResult(
        text=combined_text,
        mean_confidence=avg_conf,
        low_confidence=avg_conf < _LOW_CONFIDENCE_THRESHOLD,
    )
