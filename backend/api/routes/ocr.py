"""
POST /api/ocr — OCR Pipeline endpoint.

Accepts a PDF or image file upload and returns:
- Extracted biomarkers as structured JSON
- Raw OCR text
- Parse confidence score
"""

import tempfile
import os
from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.ocr.extractor import process_pdf_to_spatial_text, process_image_to_text, parse_text_to_json

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class OcrResponse:
    """Not using Pydantic here — we'll return a dict directly for flexibility."""
    pass


@router.post("/api/ocr")
async def run_ocr(file: UploadFile = File(...)):
    """
    Run OCR extraction on an uploaded PDF or image file.

    Returns extracted biomarkers, raw text, and confidence score.
    """
    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save uploaded file to a temp location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    try:
        # Run OCR extraction — use PDF pipeline for PDFs, image pipeline for images
        if ext == ".pdf":
            raw_text = process_pdf_to_spatial_text(tmp_path)
        else:
            raw_text = process_image_to_text(tmp_path)

        extracted_data = parse_text_to_json(raw_text)

        # Transform flat dict into biomarker list matching frontend expectations
        biomarkers = []
        for name, value in extracted_data.items():
            biomarker = {
                "name": name,
                "value": float(value) if isinstance(value, (int, float)) else 0.0,
                "unit": "",  # Unit extraction not yet implemented
                "ref_low": None,
                "ref_high": None,
                "flag": None,
            }
            biomarkers.append(biomarker)

        # Calculate a simple confidence score based on extraction success
        total_possible = len(extracted_data)
        numeric_count = sum(1 for v in extracted_data.values() if isinstance(v, (int, float)))
        parse_confidence = numeric_count / max(total_possible, 1)

        return {
            "biomarkers": biomarkers,
            "raw_text": raw_text,
            "parse_confidence": round(parse_confidence, 2),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")
    finally:
        # Clean up temp file (ignore errors on Windows file locks)
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except PermissionError:
            pass  # Windows may still hold the file; it'll be cleaned up on reboot
