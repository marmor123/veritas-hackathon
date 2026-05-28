"""
POST /api/verify — Verification Layer endpoint.

Accepts raw biomarker results (from OCR) plus medications/supplements,
returns verified results with drug interferences, quality flags, and corrected values.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.models.schemas import (
    BiomarkerResult,
    VerificationOutput,
)
from backend.verification.verifier import verify_results

router = APIRouter()


class VerificationRequest(BaseModel):
    biomarkers: List[BiomarkerResult]
    medications: Optional[List[str]] = None
    supplements: Optional[List[str]] = None


@router.post("/api/verify", response_model=VerificationOutput)
async def verify_endpoint(request: VerificationRequest) -> VerificationOutput:
    """
    Run verification layer on biomarker results.

    Returns verified results with hemolysis flags, drug interferences,
    physiological plausibility checks, and corrected values.
    """
    try:
        result = verify_results(
            biomarkers=request.biomarkers,
            medications=request.medications,
            supplements=request.supplements,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Verification error: {str(e)}",
        )
