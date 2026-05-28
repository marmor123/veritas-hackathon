"""
POST /api/analyze — Full analysis endpoint (Module 5).

Orchestrates the complete pipeline:
  1. Accepts biomarkers + medications + wearable
  2. Runs verification (Module 3)
  3. Runs RAG retrieval (Module 4)
  4. Runs LLM synthesis (Module 5)
  5. Returns AnalysisOutput for the frontend

Also supports:
  - ?demo=iron_deficiency (instant cached response, no LLM needed)
  - Graceful degradation if any stage fails
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from backend.api.models.schemas import (
    BiomarkerResult,
    AnalysisOutput,
    VerificationOutput,
)
from backend.verification.verifier import verify_results
from backend.rag.pipeline import RAGPipeline
from backend.llm.synthesizer import synthesize
from backend.llm.demo_outputs import get_demo_output, DEMO_SCENARIOS

router = APIRouter()

# Singleton RAG pipeline
_pipeline: RAGPipeline | None = None


def _get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


class AnalyzeRequest(BaseModel):
    """Request body for the full analysis endpoint."""
    biomarkers: List[BiomarkerResult]
    medications: Optional[List[str]] = None
    supplements: Optional[List[str]] = None
    wearable_data: Optional[dict] = None


@router.post("/api/analyze", response_model=AnalysisOutput)
async def analyze(
    request: AnalyzeRequest,
    demo: Optional[str] = Query(None, description="Demo scenario name for instant cached response"),
) -> AnalysisOutput:
    """
    Run the full analysis pipeline: Verify → RAG → LLM Synthesis.

    Query params:
        demo: If provided, returns a pre-cached demo output instantly.
              Valid values: iron_deficiency, metabolic_syndrome, biotin_interference, hemolysis_artifact
    """
    # Demo mode: instant cached response
    if demo:
        demo_output = get_demo_output(demo)
        if demo_output:
            return demo_output
        raise HTTPException(
            status_code=400,
            detail=f"Unknown demo scenario: '{demo}'. Valid: {list(DEMO_SCENARIOS.keys())}",
        )

    try:
        # ── Stage 1: Verification (Module 3) ─────────────────────────────
        logger.info("[Analyze] Stage 1: Running verification...")
        verification = verify_results(
            biomarkers=request.biomarkers,
            medications=request.medications,
            supplements=request.supplements,
        )
        logger.info(
            "[Analyze] Stage 1 DONE — %d verified results, %d quality flags, %d drug interferences",
            len(verification.verified_results),
            len(verification.quality_flags),
            len(verification.drug_interferences),
        )

        # ── Early halt: if any quality flag has severity "high", stop ────
        high_severity_flags = [
            flag for flag in verification.quality_flags
            if flag.severity == "high"
        ]
        if high_severity_flags:
            return AnalysisOutput(
                summary=(
                    "Your results could not be analyzed because one or more values "
                    "appear unreliable due to sample quality issues. "
                    "This is likely a collection or handling error, not a medical problem."
                ),
                patterns=[],
                verification_alerts=[
                    {
                        "biomarker": ", ".join(flag.affected_biomarkers),
                        "issue": flag.detail,
                        "recommendation": "Please consider repeating the blood test with a fresh sample.",
                    }
                    for flag in high_severity_flags
                ],
                disclaimer=(
                    "This analysis is for informational purposes only and does not "
                    "constitute medical advice. Please discuss these results with "
                    "your healthcare provider."
                ),
            )

        # ── Stage 2: RAG Retrieval (Module 4) ────────────────────────────
        logger.info("[Analyze] Stage 2: Running RAG retrieval...")
        pipeline = _get_pipeline()
        rag_result = pipeline.run(
            verified_results=verification.verified_results,
            medications=request.medications,
            wearable_data=request.wearable_data,
        )
        logger.info(
            "[Analyze] Stage 2 DONE — citations length: %d chars, clinical_graph present: %s",
            len(rag_result.get("citations_formatted", "")),
            "clinical_graph" in rag_result,
        )

        # ── Stage 3: LLM Synthesis (Module 5) ────────────────────────────
        logger.info("[Analyze] Stage 3: Running LLM synthesis...")
        analysis = synthesize(
            verified_results=verification.verified_results,
            citations_formatted=rag_result["citations_formatted"],
            verification=verification,
            medications=request.medications,
            wearable_data=request.wearable_data,
        )
        logger.info("[Analyze] Stage 3 DONE — summary: %s", analysis.summary[:80])

        # Attach the clinical graph from RAG to the output
        analysis.clinical_graph = rag_result.get("clinical_graph")

        # Attach non-critical verification alerts (low/medium flags + drug interferences)
        if verification.drug_interferences:
            for interference in verification.drug_interferences:
                analysis.verification_alerts.append({
                    "biomarker": interference.biomarker,
                    "issue": f"Drug interference: {interference.drug} {interference.effect} {interference.biomarker}",
                    "recommendation": interference.recommendation,
                })

        low_medium_flags = [
            flag for flag in verification.quality_flags
            if flag.severity in ("low", "medium")
        ]
        for flag in low_medium_flags:
            analysis.verification_alerts.append({
                "biomarker": ", ".join(flag.affected_biomarkers),
                "issue": flag.detail,
                "recommendation": "Discuss with your healthcare provider.",
            })

        return analysis

    except Exception as e:
        # If anything fails, try to return partial results
        logger.error("[Analyze] Pipeline error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis pipeline error: {str(e)}",
        )


@router.get("/api/analyze/demos")
async def list_demos():
    """List available demo scenarios."""
    return {
        "scenarios": list(DEMO_SCENARIOS.keys()),
        "usage": "POST /api/analyze?demo=iron_deficiency",
    }
