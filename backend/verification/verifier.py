"""
Module 3 entry point: verify_results()

Orchestrates all verification sub-modules:
  - Hemolysis detection
  - Drug interference
  - Physiological plausibility
  - Corrected values

Returns a VerificationOutput that feeds directly into the RAG engine (Module 4).
"""

from typing import Optional

from backend.api.models.schemas import (
    BiomarkerResult,
    VerifiedResult,
    VerificationOutput,
    QualityFlag,
    DrugInterference,
)
from backend.verification.hemolysis import detect_hemolysis
from backend.verification.drug_interference import detect_drug_interferences
from backend.verification.plausibility import check_plausibility
from backend.verification.corrected_values import compute_corrected_values


def verify_results(
    biomarkers: list[BiomarkerResult],
    medications: list[str] | None = None,
    supplements: list[str] | None = None,
) -> VerificationOutput:
    """
    Run the full verification pipeline on a set of biomarker results.

    Args:
        biomarkers: Raw biomarker results from OCR (Module 1)
        medications: Patient's medication list (from Context Collector, Module 2)
        supplements: Patient's supplement list (treated same as medications)

    Returns:
        VerificationOutput with:
          - verified_results: All biomarkers re-typed with abnormal/normal flag
          - drug_interferences: Drug-lab effects detected
          - corrected_values: Calculated/corrected values
          - quality_flags: Hemolysis and plausibility warnings
    """
    # Combine medications + supplements (same logic for both)
    all_drugs = []
    if medications:
        all_drugs.extend(medications)
    if supplements:
        all_drugs.extend(supplements)

    # Run all checks
    hemolysis_flags = detect_hemolysis(biomarkers)
    plausibility_flags = check_plausibility(biomarkers)
    drug_interferences = detect_drug_interferences(biomarkers, all_drugs)
    corrected = compute_corrected_values(biomarkers)

    # Build verified results
    verified_results = [_to_verified_result(b) for b in biomarkers]

    # Combine all quality flags
    quality_flags = hemolysis_flags + plausibility_flags

    return VerificationOutput(
        verified_results=verified_results,
        drug_interferences=drug_interferences,
        corrected_values=corrected,
        quality_flags=quality_flags,
    )


def _to_verified_result(biomarker: BiomarkerResult) -> VerifiedResult:
    """Convert a BiomarkerResult to a VerifiedResult with normalized flag."""
    flagged = False
    flag_reason = None

    # Check OCR-provided flag (multiple formats)
    if biomarker.flag:
        flag_lower = biomarker.flag.lower().strip()
        if flag_lower in ("h", "high"):
            flagged = True
            flag_reason = "Above reference range"
        elif flag_lower in ("l", "low"):
            flagged = True
            flag_reason = "Below reference range"
        elif flag_lower in ("normal", "n"):
            flagged = False

    # Cross-check with reference range
    if biomarker.ref_low is not None and biomarker.value < biomarker.ref_low:
        flagged = True
        flag_reason = f"Below reference range ({biomarker.ref_low})"
    elif biomarker.ref_high is not None and biomarker.value > biomarker.ref_high:
        flagged = True
        flag_reason = f"Above reference range ({biomarker.ref_high})"

    return VerifiedResult(
        biomarker=biomarker.name,
        value=biomarker.value,
        unit=biomarker.unit,
        ref_low=biomarker.ref_low,
        ref_high=biomarker.ref_high,
        flagged=flagged,
        flag_reason=flag_reason,
    )
