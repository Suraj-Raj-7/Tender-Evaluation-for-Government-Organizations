"""
backend/app/services/ocr.py
--------------------------------
Purpose: Extracts text from any uploaded document, whether it's a
digital PDF (real selectable text) or a scanned PDF/photo (needs OCR).
Returns the extracted text along with a confidence score, so low-quality
scans can later be treated as REVIEW instead of an automatic FAIL.

Why this file exists: Every uploaded document -- a tender's NIT, or a
bidder's supporting documents -- must pass through here before its text
can be used anywhere else (AI extraction in Phase 3, evidence in Phase 4).
"""

import pdfplumber
import pytesseract
from pytesseract import Output
from pdf2image import convert_from_path
from PIL import Image


def _extract_with_pdfplumber(file_path: str):
    """
    Purpose: Attempts to read real, selectable text directly out of a
    PDF -- the fast, accurate path for digital PDFs.

    Where it gets its data: file_path is the local disk path of a
    downloaded document (the caller writes MinIO bytes to a temp file
    first, then passes that path here).

    Where it's used: Called first by extract_text() below, for any file
    ending in .pdf.

    Returns: (text, page_count) -- confidence is always 1.0 for this
    path, since the text was directly present, not guessed by OCR.
    """
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        text_parts = [page.extract_text() or "" for page in pdf.pages]
        full_text = "\n".join(text_parts)
    return full_text, page_count


def _extract_with_tesseract_image(image: Image.Image):
    """
    Purpose: Runs OCR on a single image (one page), and computes the
    average confidence across every word Tesseract recognized on it.

    Where it gets its data: image is a PIL Image object -- either a
    directly uploaded photo, or one page of a scanned PDF converted to
    an image by pdf2image.

    Where it's used: Called once per page by extract_text() below, for
    both scanned PDFs and direct image uploads.

    Returns: (text, confidence) for this one page.
    """
    data = pytesseract.image_to_data(image, lang="eng+hin", output_type=Output.DICT)

    words = []
    confidences = []
    for i, word in enumerate(data["text"]):
        conf = int(data["conf"][i])
        if word.strip() and conf > 0:
            words.append(word)
            confidences.append(conf)

    page_text = " ".join(words)
    # Tesseract gives confidence as 0-100; convert to our 0.0-1.0 scale.
    page_confidence = (sum(confidences) / len(confidences) / 100) if confidences else 0.0
    return page_text, page_confidence


def extract_text(file_path: str, is_image: bool = False):
    """
    Purpose: The single entry point for extracting text from any
    uploaded document. Automatically decides whether to use pdfplumber
    (digital PDF) or Tesseract OCR (scanned PDF or photo).

    Where it gets its data: file_path is a local temp file path (the
    caller downloads bytes from MinIO via storage.py's download_file()
    and writes them to a temp file before calling this). is_image tells
    it whether the file is a photo (jpg/png) rather than a PDF.

    Where it's used: Will be called by Celery tasks in Phase 3, right
    after a document is uploaded, to fill in a Document row's
    extracted_text, ocr_confidence, is_scanned, and page_count fields.

    Returns: (text: str, confidence: float, page_count: int, is_scanned: bool)
    Never raises an exception -- on any failure, returns a safe empty
    result instead of crashing the caller (per the project's "never
    silently disqualify a bidder due to a technical error" principle).
    """
    try:
        if is_image:
            image = Image.open(file_path)
            text, confidence = _extract_with_tesseract_image(image)
            return text, confidence, 1, True

        # Try the fast, accurate path first: real text already in the PDF.
        text, page_count = _extract_with_pdfplumber(file_path)

        # Heuristic: if there's less than ~50 characters of real text per
        # page on average, this PDF is almost certainly just scanned
        # images with no real text layer -- fall back to OCR.
        avg_chars_per_page = len(text) / page_count if page_count else 0
        if avg_chars_per_page >= 50:
            return text, 1.0, page_count, False

        # Fallback: convert each PDF page to an image, then OCR each one.
        images = convert_from_path(file_path)
        page_texts = []
        page_confidences = []
        for image in images:
            page_text, page_confidence = _extract_with_tesseract_image(image)
            page_texts.append(page_text)
            page_confidences.append(page_confidence)

        full_text = "\n".join(page_texts)
        overall_confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
        return full_text, overall_confidence, len(images), True

    except Exception:
        # Per spec: never crash on a bad/corrupt file. A failed
        # extraction becomes a REVIEW case downstream (0.0 confidence),
        # never an automatic FAIL.
        return "", 0.0, 0, True