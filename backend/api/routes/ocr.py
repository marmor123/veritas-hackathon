"""
POST /api/ocr — OCR Pipeline endpoint (Module 1).

Accepts a PDF or image file, runs OCR, and returns structured biomarker data.
"""

import os
import tempfile
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from backend.api.models.schemas import BiomarkerResult
from backend.ocr.extractor import (
    process_pdf_to_spatial_text,
    process_image_to_text,
    parse_text_to_json,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class OcrResponse(BaseModel):
    biomarkers: List[BiomarkerResult]
    raw_text: str
    parse_confidence: float


# Reference ranges for common biomarkers (used when OCR doesn't extract them)
REFERENCE_RANGES = {
    "HEMOGLOBIN": (12.0, 16.0, "g/dL"),
    "HEMATOCRIT": (36.0, 46.0, "%"),
    "MCV": (80.0, 100.0, "fL"),
    "MCH": (27.0, 33.0, "pg"),
    "MCHC": (32.0, 36.0, "g/dL"),
    "RDW": (11.5, 14.5, "%"),
    "WBC": (4500.0, 11000.0, "/µL"),
    "PLATELETS": (150000.0, 400000.0, "/µL"),
    "NEUTROPHILS": (40.0, 70.0, "%"),
    "LYMPHOCYTES": (20.0, 40.0, "%"),
    "MONOCYTES": (2.0, 8.0, "%"),
    "EOSINOPHILS": (1.0, 4.0, "%"),
    "BASOPHILS": (0.0, 1.0, "%"),
    "ESR": (0.0, 20.0, "mm/hr"),
    "MPV": (7.5, 11.5, "fL"),
    "GLUCOSE": (70.0, 100.0, "mg/dL"),
    "HBA1C": (4.0, 5.6, "%"),
    "CREATININE": (0.6, 1.2, "mg/dL"),
    "UREA": (7.0, 20.0, "mg/dL"),
    "BUN": (7.0, 20.0, "mg/dL"),
    "URIC_ACID": (3.5, 7.2, "mg/dL"),
    "ALT": (7.0, 56.0, "U/L"),
    "AST": (10.0, 40.0, "U/L"),
    "ALKP": (44.0, 147.0, "U/L"),
    "TOTAL_PROTEIN": (6.0, 8.3, "g/dL"),
    "ALBUMIN": (3.5, 5.5, "g/dL"),
    "BILIRUBIN_TOTAL": (0.1, 1.2, "mg/dL"),
    "CHOLESTEROL": (0.0, 200.0, "mg/dL"),
    "TRIGLYCERIDES": (0.0, 150.0, "mg/dL"),
    "HDL": (40.0, 60.0, "mg/dL"),
    "LDL": (0.0, 100.0, "mg/dL"),
    "SODIUM": (136.0, 145.0, "mEq/L"),
    "POTASSIUM": (3.5, 5.0, "mEq/L"),
    "CHLORIDE": (98.0, 106.0, "mEq/L"),
    "CALCIUM": (8.5, 10.5, "mg/dL"),
    "IRON": (60.0, 170.0, "µg/dL"),
    "FERRITIN": (15.0, 150.0, "ng/mL"),
    "TSH": (0.4, 4.0, "mIU/L"),
    "T3": (80.0, 200.0, "ng/dL"),
    "T4": (5.0, 12.0, "µg/dL"),
    "VITAMIN_D": (30.0, 100.0, "ng/mL"),
    "VITAMIN_B12": (200.0, 900.0, "pg/mL"),
    "CRP": (0.0, 3.0, "mg/L"),
}


@router.post("/api/ocr", response_model=OcrResponse)
async def run_ocr(file: UploadFile = File(...)) -> OcrResponse:
    """
    Run OCR on an uploaded blood test PDF or image.
    Returns structured biomarker data.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    try:
        if ext == ".pdf":
            raw_text = process_pdf_to_spatial_text(tmp_path)
        else:
            raw_text = process_image_to_text(tmp_path)

        parsed = parse_text_to_json(raw_text)

        biomarkers: List[BiomarkerResult] = []
        for name, value in parsed.items():
            if not isinstance(value, (int, float)):
                continue  # Skip qualitative results (Negative, Positive, etc.)

            ref_low, ref_high, unit = REFERENCE_RANGES.get(name, (None, None, ""))

            flag = None
            if ref_low is not None and value < ref_low:
                flag = "L"
            elif ref_high is not None and value > ref_high:
                flag = "H"

            display_name = name.replace("_", " ").title()

            biomarkers.append(BiomarkerResult(
                name=display_name,
                value=float(value),
                unit=unit,
                ref_low=ref_low,
                ref_high=ref_high,
                flag=flag,
            ))

        total_possible = len(REFERENCE_RANGES)
        confidence = min(len(biomarkers) / max(total_possible * 0.3, 1), 1.0)

        return OcrResponse(
            biomarkers=biomarkers,
            raw_text=raw_text[:2000],
            parse_confidence=round(confidence, 2),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing error: {str(e)}",
        )
    finally:
        try:
            os.unlink(tmp_path)
        except PermissionError:
            pass
