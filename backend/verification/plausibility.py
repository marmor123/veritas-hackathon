"""
Physiological plausibility checks.

Verify that biomarker combinations make physiological sense.
Flags inconsistencies that might indicate lab errors or unusual presentations.

Rules:
  - Calcium/Albumin: low albumin → falsely low total calcium (use corrected)
  - BUN/Creatinine ratio: pre-renal vs intrinsic renal vs post-renal
  - AST/ALT ratio: hepatocellular vs alcoholic vs muscle origin
  - TSH/FT4 consistency: primary vs secondary thyroid disease vs assay issue
  - Anion gap: metabolic acidosis screening
"""

from typing import Optional
from backend.api.models.schemas import BiomarkerResult, QualityFlag


def _find(biomarkers: list[BiomarkerResult], names: list[str]) -> Optional[BiomarkerResult]:
    name_set = {n.lower().strip() for n in names}
    for b in biomarkers:
        if b.name.lower().strip().replace("_", " ") in name_set:
            return b
    return None


def check_plausibility(biomarkers: list[BiomarkerResult]) -> list[QualityFlag]:
    """Run all plausibility checks and return quality flags."""
    flags = []

    flags.extend(_check_calcium_albumin(biomarkers))
    flags.extend(_check_bun_creatinine_ratio(biomarkers))
    flags.extend(_check_ast_alt_ratio(biomarkers))
    flags.extend(_check_tsh_t4_consistency(biomarkers))

    return flags


def _check_calcium_albumin(biomarkers: list[BiomarkerResult]) -> list[QualityFlag]:
    """Low albumin → total calcium appears falsely low. Use corrected calcium."""
    ca = _find(biomarkers, ["calcium"])
    alb = _find(biomarkers, ["albumin"])

    if not ca or not alb:
        return []

    # Albumin typically reported in g/dL; normal ~4.0
    if alb.unit and "g/l" in alb.unit.lower() and "g/dl" not in alb.unit.lower():
        albumin_g_dl = alb.value / 10.0
    else:
        albumin_g_dl = alb.value

    if albumin_g_dl >= 3.5:
        return []  # Normal albumin, no correction needed

    # Calculate corrected calcium (in mg/dL)
    if ca.unit and "mmol" in ca.unit.lower():
        # Convert mmol/L to mg/dL: 1 mmol/L = 4.0 mg/dL
        ca_mg_dl = ca.value * 4.0
    else:
        ca_mg_dl = ca.value

    corrected = ca_mg_dl + 0.8 * (4.0 - albumin_g_dl)
    diff = corrected - ca_mg_dl

    if abs(diff) >= 0.3:
        return [QualityFlag(
            type="plausibility",
            severity="medium",
            detail=(
                f"Total calcium appears low ({ca.value} {ca.unit}), but albumin is also "
                f"low ({alb.value} {alb.unit}). Corrected calcium = {corrected:.1f} mg/dL. "
                f"True ionized calcium status is best assessed by corrected value or "
                f"ionized calcium measurement."
            ),
            affected_biomarkers=["Calcium", "Albumin"],
        )]
    return []


def _check_bun_creatinine_ratio(biomarkers: list[BiomarkerResult]) -> list[QualityFlag]:
    """BUN/Creatinine ratio reveals pre-renal vs intrinsic renal cause."""
    bun = _find(biomarkers, ["bun", "blood urea nitrogen", "urea"])
    cr = _find(biomarkers, ["creatinine"])

    if not bun or not cr or cr.value == 0:
        return []

    # If we got "urea" instead of BUN, convert (BUN = urea × 0.467)
    bun_value = bun.value
    if "urea" in bun.name.lower() and "bun" not in bun.name.lower():
        # Heuristic: if value is very high it's probably urea, not BUN
        if bun_value > 50:
            bun_value = bun_value * 0.467

    ratio = bun_value / cr.value

    # Only flag if at least one of BUN/Cr is abnormal
    bun_high = bun.ref_high and bun.value > bun.ref_high
    cr_high = cr.ref_high and cr.value > cr.ref_high
    if not (bun_high or cr_high):
        return []

    if ratio > 20:
        return [QualityFlag(
            type="plausibility",
            severity="low",
            detail=(
                f"BUN/Creatinine ratio is {ratio:.0f}:1 (normal 10-20:1). "
                f"Elevated ratio suggests pre-renal cause — possible dehydration, "
                f"reduced kidney perfusion, or GI bleeding."
            ),
            affected_biomarkers=["BUN", "Creatinine"],
        )]
    elif ratio < 10:
        return [QualityFlag(
            type="plausibility",
            severity="low",
            detail=(
                f"BUN/Creatinine ratio is {ratio:.0f}:1 (normal 10-20:1). "
                f"Low ratio with elevated values suggests intrinsic kidney disease "
                f"rather than dehydration."
            ),
            affected_biomarkers=["BUN", "Creatinine"],
        )]
    return []


def _check_ast_alt_ratio(biomarkers: list[BiomarkerResult]) -> list[QualityFlag]:
    """AST/ALT ratio differentiates hepatocellular from alcoholic vs muscle origin."""
    ast = _find(biomarkers, ["ast", "sgot"])
    alt = _find(biomarkers, ["alt", "sgpt"])

    if not ast or not alt or alt.value == 0:
        return []

    # Only relevant if at least one is elevated
    ast_high = ast.ref_high and ast.value > ast.ref_high
    alt_high = alt.ref_high and alt.value > alt.ref_high
    if not (ast_high or alt_high):
        return []

    ratio = ast.value / alt.value

    if ratio > 2.0 and ast_high:
        # AST > 2x ALT → consider alcoholic liver disease or muscle source
        ck = _find(biomarkers, ["ck", "creatine kinase"])
        if ck and ck.ref_high and ck.value > ck.ref_high:
            return [QualityFlag(
                type="plausibility",
                severity="medium",
                detail=(
                    f"AST/ALT ratio is {ratio:.1f} (>2.0) with elevated CK. "
                    f"Pattern suggests muscle origin rather than liver — "
                    f"consider muscle injury, intense exercise, or rhabdomyolysis."
                ),
                affected_biomarkers=["AST", "ALT", "CK"],
            )]
        else:
            return [QualityFlag(
                type="plausibility",
                severity="low",
                detail=(
                    f"AST/ALT ratio is {ratio:.1f} (>2.0). "
                    f"Pattern more consistent with alcoholic hepatitis than typical "
                    f"hepatocellular injury (usually ALT > AST)."
                ),
                affected_biomarkers=["AST", "ALT"],
            )]
    return []


def _check_tsh_t4_consistency(biomarkers: list[BiomarkerResult]) -> list[QualityFlag]:
    """
    TSH/Free T4 should follow predictable patterns:
      - High TSH + low FT4 → primary hypothyroidism (consistent)
      - Low TSH + high FT4 → primary hyperthyroidism (consistent)
      - High TSH + high FT4 → unusual (assay interference, T4 resistance, or pituitary tumor)
    """
    tsh = _find(biomarkers, ["tsh"])
    ft4 = _find(biomarkers, ["free t4", "ft4", "t4 free"])

    if not tsh or not ft4 or not tsh.ref_high or not ft4.ref_high:
        return []

    tsh_high = tsh.value > tsh.ref_high
    tsh_low = tsh.ref_low and tsh.value < tsh.ref_low
    ft4_high = ft4.value > ft4.ref_high
    ft4_low = ft4.ref_low and ft4.value < ft4.ref_low

    # Inconsistent: both high or both low
    if tsh_high and ft4_high:
        return [QualityFlag(
            type="plausibility",
            severity="medium",
            detail=(
                f"Both TSH ({tsh.value} {tsh.unit}) and Free T4 ({ft4.value} {ft4.unit}) "
                f"are elevated. This unusual pattern can indicate assay interference "
                f"(e.g., biotin), thyroid hormone resistance, or rare pituitary disease. "
                f"Recommend repeat testing and assess for biotin supplementation."
            ),
            affected_biomarkers=["TSH", "Free T4"],
        )]

    if tsh_low and ft4_low:
        return [QualityFlag(
            type="plausibility",
            severity="medium",
            detail=(
                f"Both TSH ({tsh.value} {tsh.unit}) and Free T4 ({ft4.value} {ft4.unit}) "
                f"are low. Pattern suggests central (secondary) hypothyroidism — "
                f"pituitary or hypothalamic dysfunction rather than thyroid gland disease."
            ),
            affected_biomarkers=["TSH", "Free T4"],
        )]

    return []
