# app/services/extract_text.py
from pathlib import Path
import pdfplumber
from app.services.ocr import ocr_provider
from fastapi import UploadFile
from app.storage import storage

def extract_from_path(path: str) -> tuple[str, float, int, bool]:
    """Returns: (text, avg_confidence, page_count, is_scanned)"""
    p = Path(path)
    suffix = p.suffix.lower()
    
    if suffix in [".png", ".jpg", ".jpeg"]:
        res = ocr_provider.extract_image(str(p))
        return res.text, res.confidence, 1, True

    if suffix == ".pdf":
        text_parts = []
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
        
        joined = "\n".join(text_parts).strip()
        # If text is too short, it's likely a scanned PDF
        if len(joined) < 50 * page_count:
            # This line will now work because we added extract_pdf_pages to ocr.py
            res = ocr_provider.extract_pdf_pages(path)
            return res.text, res.confidence, page_count, True
            
        return joined, 1.0, page_count, False
    
    return "", 0.0, 0, False

def process_files(files: list[UploadFile]) -> tuple[str, float]:
    """
    Processes multiple uploaded files, merges their text, 
    and calculates average OCR confidence.
    """
    combined_text = ""
    total_conf = 0.0
    file_count = 0

    for file in files:
        if not file.filename:
            continue
        # Save file to temporary storage
        path, size = storage.save(file.filename, file.file)
        # Extract text
        text, conf, pages, scanned = extract_from_path(path)
        
        combined_text += f"\n--- DOCUMENT: {file.filename} ---\n{text}"
        total_conf += conf
        file_count += 1

    avg_conf = total_conf / file_count if file_count > 0 else 0.0
    return combined_text, avg_conf