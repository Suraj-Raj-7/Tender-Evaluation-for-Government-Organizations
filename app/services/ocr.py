# app/services/ocr.py
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import os

class OCRResult:
    def __init__(self, text: str, confidence: float):
        self.text = text
        self.confidence = confidence

class TesseractProvider:
    def __init__(self):
        # Default path for Tesseract on Windows as per README
        self.tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(self.tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def extract_image(self, image_path: str) -> OCRResult:
        """Extracts text from a single image file."""
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        # Simple confidence heuristic for Tesseract
        return OCRResult(text, 0.9)

    def extract_pdf_pages(self, pdf_path: str) -> OCRResult:
        """
        Converts PDF pages to images and runs OCR on each.
        This fixes the AttributeError in extract_text.py.
        """
        try:
            # Convert PDF to list of PIL Image objects
            images = convert_from_path(pdf_path)
            full_text = []
            
            for i, image in enumerate(images):
                page_text = pytesseract.image_to_string(image)
                full_text.append(f"--- Page {i+1} ---\n{page_text}")
            
            return OCRResult("\n".join(full_text), 0.85)
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return OCRResult("OCR Failed to process PDF.", 0.0)

# Initialize the provider
ocr_provider = TesseractProvider()