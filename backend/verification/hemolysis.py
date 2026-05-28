"""
Hemolysis detection — catches pre-analytical errors that falsely elevate certain biomarkers.

When red blood cells burst during/after collection, they release intracellular contents
into serum, falsely elevating potassium, LDH, and AST. This is the most common reason
for spuriously abnormal results.

Rules:
  1. K+ > 6.0 with normal kidney function → likely hemolysis (true hyperkalemia is rare in normal kidneys)
  2. K+ > 7.0 → strongly suspect artifact (incompatible with normal life)
  3. LDH > 2x ULN AND AST not proportionally elevated → possible hemolysis
  4. Very low glucose (<40 mg/dL) without critical findings → possible sample aging
"""

from typing import Optional
from backend.api.models.schemas import BiomarkerResult, QualityFlag


# Reference upper limits used when biomarker doesn't include ref ranges
DEFAULT_REF_UPPER = {
    "potassium": 5.0,
    "ldh": 280.0,
    "ast": 35.0,
    "alt": 35.0,
    "egfr": None,  # lower-better, threshold is >60
    "creatinine": 1.3,
    "glucose": 100.0,
}


def _normalize_name(name: str) -> str:
    """Normalize biomarker name for matching."""
    return name.lower().strip().replace("_", " ")


def _find_biomarker(biomarkers: list[BiomarkerResult], names: list[str]) -> Optional[BiomarkerResult]:
    """Find first biomarker matching any of the given names (case-insensitive)."""
    name_set = {n.lower() for n in names}
    for b in biomarkers:
        if _normalize_name(b.name) in name_set:
            return b
    return None


def detect_hemolysis(biomarkers: list[BiomarkerResult]) -> list[QualityFlag]:
    """Run all hemolysis detection rules and return quality flags."""
    flags = []

    # Rule 1+2: Hyperkalemia
    k = _find_biomarker(biomarkers, ["potassium", "k", "k+"])
    egfr = _find_biomarker(biomarkers, ["egfr", "gfr"])
    creatinine = _find_biomarker(biomarkers, ["creatinine"])

    if k:
        # Rule 2: Extreme K+ > 7.0 — almost always artifact
        if k.value > 7.0:
            flags.append(QualityFlag(
                type="hemolysis",
                severity="high",
                detail=(
                    f"Potassium {k.value} {k.unit} is critically elevated. "
                    f"True hyperkalemia at this level is incompatible with normal life — "
                    f"very likely a sample collection artifact (hemolysis). "
                    f"Recommend repeat draw with careful technique."
                ),
                affected_biomarkers=["Potassium"],
            ))
        # Rule 1: Mild-moderate K+ elevation with normal kidneys
        elif k.value > 6.0:
            kidney_normal = (
                (egfr and egfr.value > 60) or
                (creatinine and creatinine.value < 1.3) or
                (egfr is None and creatinine is None)
            )
            if kidney_normal:
                flags.append(QualityFlag(
                    type="hemolysis",
                    severity="medium",
                    detail=(
                        f"Potassium {k.value} {k.unit} is elevated but kidney function appears normal. "
                        f"True hyperkalemia is uncommon with normal kidneys — "
                        f"possible sample hemolysis releasing intracellular K+. "
                        f"Recommend repeat with careful collection."
                    ),
                    affected_biomarkers=["Potassium"],
                ))

    # Rule 3: LDH disproportionately elevated vs AST
    ldh = _find_biomarker(biomarkers, ["ldh"])
    ast = _find_biomarker(biomarkers, ["ast", "sgot"])

    if ldh and ast and ldh.ref_high and ast.ref_high:
        ldh_ratio = ldh.value / ldh.ref_high
        ast_ratio = ast.value / ast.ref_high
        if ldh_ratio > 2.0 and ast_ratio < 1.5:
            flags.append(QualityFlag(
                type="hemolysis",
                severity="medium",
                detail=(
                    f"LDH ({ldh.value} {ldh.unit}) is {ldh_ratio:.1f}x upper limit "
                    f"but AST is only {ast_ratio:.1f}x — disproportionate elevation "
                    f"suggests RBC lysis (LDH is highly concentrated in red cells). "
                    f"Consider possible hemolysis artifact."
                ),
                affected_biomarkers=["LDH", "AST"],
            ))

    # Rule 4: Very low glucose without other critical findings
    glucose = _find_biomarker(biomarkers, ["glucose"])
    if glucose and glucose.value < 40:
        # Check if other biomarkers suggest a real metabolic crisis
        critical_signs = False
        # If we have HbA1c showing diabetes or other concerning findings, less likely artifact
        hba1c = _find_biomarker(biomarkers, ["hba1c", "a1c"])
        if hba1c and hba1c.value > 7:
            critical_signs = True

        if not critical_signs:
            flags.append(QualityFlag(
                type="pre_analytical",
                severity="medium",
                detail=(
                    f"Glucose {glucose.value} {glucose.unit} is critically low. "
                    f"Without supporting clinical findings, this may be sample aging — "
                    f"red blood cells consume glucose during transport delays. "
                    f"Recommend repeat with prompt processing."
                ),
                affected_biomarkers=["Glucose"],
            ))

    return flags
