"""
Compute corrected/derived values from biomarker measurements.

Implements:
  - Corrected Calcium (for hypoalbuminemia)
  - Anion Gap (Na - (Cl + HCO3))
  - LDL Cholesterol (Friedewald formula, when TG < 400)
  - Corrected Sodium for hyperglycemia
"""

from typing import Optional
from backend.api.models.schemas import BiomarkerResult


def _find(biomarkers: list[BiomarkerResult], names: list[str]) -> Optional[BiomarkerResult]:
    name_set = {n.lower().strip() for n in names}
    for b in biomarkers:
        if b.name.lower().strip().replace("_", " ") in name_set:
            return b
    return None


def compute_corrected_values(biomarkers: list[BiomarkerResult]) -> list[dict]:
    """
    Compute all applicable corrected values.

    Returns:
        List of dicts: {name, raw_value, corrected_value, formula, unit}
    """
    results = []

    # Corrected Calcium
    corrected_ca = _corrected_calcium(biomarkers)
    if corrected_ca:
        results.append(corrected_ca)

    # Anion Gap
    anion_gap = _anion_gap(biomarkers)
    if anion_gap:
        results.append(anion_gap)

    # LDL via Friedewald
    ldl = _ldl_friedewald(biomarkers)
    if ldl:
        results.append(ldl)

    # Corrected Sodium for hyperglycemia
    corrected_na = _corrected_sodium(biomarkers)
    if corrected_na:
        results.append(corrected_na)

    return results


def _corrected_calcium(biomarkers: list[BiomarkerResult]) -> Optional[dict]:
    """Corrected Ca = measured Ca + 0.8 × (4.0 − albumin g/dL)."""
    ca = _find(biomarkers, ["calcium"])
    alb = _find(biomarkers, ["albumin"])

    if not ca or not alb:
        return None

    # Normalize albumin to g/dL
    if alb.unit and "g/l" in alb.unit.lower() and "g/dl" not in alb.unit.lower():
        albumin_g_dl = alb.value / 10.0
    else:
        albumin_g_dl = alb.value

    if albumin_g_dl >= 3.5:
        return None  # No correction needed

    # Normalize calcium to mg/dL for the formula
    if ca.unit and "mmol" in ca.unit.lower():
        ca_mg_dl = ca.value * 4.0
    else:
        ca_mg_dl = ca.value

    corrected = ca_mg_dl + 0.8 * (4.0 - albumin_g_dl)

    return {
        "name": "Corrected Calcium",
        "raw_value": round(ca.value, 2),
        "corrected_value": round(corrected, 2),
        "formula": "Ca + 0.8 × (4.0 − albumin g/dL)",
        "unit": "mg/dL",
        "interpretation": (
            "Corrects for low albumin which reduces total measured calcium without "
            "affecting biologically active ionized calcium."
        ),
    }


def _anion_gap(biomarkers: list[BiomarkerResult]) -> Optional[dict]:
    """Anion Gap = Na − (Cl + HCO3). Normal: 8-12 mmol/L."""
    na = _find(biomarkers, ["sodium", "na", "na+"])
    cl = _find(biomarkers, ["chloride", "cl", "cl-"])
    hco3 = _find(biomarkers, ["bicarbonate", "co2", "hco3"])

    if not (na and cl and hco3):
        return None

    gap = na.value - (cl.value + hco3.value)

    interpretation = "Within normal range (8-12)."
    if gap > 12:
        interpretation = (
            "Elevated anion gap suggests metabolic acidosis. "
            "Common causes (MUDPILES): methanol, uremia, DKA, paraldehyde, "
            "INH/iron, lactate, ethylene glycol, salicylates."
        )
    elif gap < 8:
        interpretation = (
            "Low anion gap is uncommon — consider hypoalbuminemia, multiple myeloma, "
            "or lab error."
        )

    return {
        "name": "Anion Gap",
        "raw_value": None,
        "corrected_value": round(gap, 1),
        "formula": "Na − (Cl + HCO3)",
        "unit": "mmol/L",
        "interpretation": interpretation,
    }


def _ldl_friedewald(biomarkers: list[BiomarkerResult]) -> Optional[dict]:
    """LDL = Total Cholesterol − HDL − (Triglycerides / 5). Valid when TG < 400 mg/dL."""
    tc = _find(biomarkers, ["cholesterol", "total cholesterol"])
    hdl = _find(biomarkers, ["hdl", "hdl cholesterol"])
    tg = _find(biomarkers, ["triglycerides", "triglyceride"])

    if not (tc and hdl and tg):
        return None

    # Already have direct LDL? Skip
    direct_ldl = _find(biomarkers, ["ldl", "ldl cholesterol", "direct ldl"])
    if direct_ldl:
        return None

    # Validate units (should all be mg/dL — common in US)
    if tg.value >= 400:
        return {
            "name": "LDL Cholesterol",
            "raw_value": None,
            "corrected_value": None,
            "formula": "Friedewald not applicable (TG ≥ 400)",
            "unit": "mg/dL",
            "interpretation": (
                f"Triglycerides are {tg.value} mg/dL — Friedewald formula is unreliable "
                f"above 400. Direct LDL measurement recommended."
            ),
        }

    ldl_value = tc.value - hdl.value - (tg.value / 5.0)

    return {
        "name": "LDL Cholesterol (calculated)",
        "raw_value": None,
        "corrected_value": round(ldl_value, 1),
        "formula": "TC − HDL − (TG/5) [Friedewald]",
        "unit": "mg/dL",
        "interpretation": (
            f"Calculated LDL = {ldl_value:.0f} mg/dL. "
            f"Use direct LDL measurement if TG ≥ 400 or for high-precision needs."
        ),
    }


def _corrected_sodium(biomarkers: list[BiomarkerResult]) -> Optional[dict]:
    """Corrected Na = measured Na + 0.016 × (glucose − 100), when glucose > 200 mg/dL."""
    na = _find(biomarkers, ["sodium", "na", "na+"])
    glucose = _find(biomarkers, ["glucose"])

    if not na or not glucose:
        return None

    # Normalize glucose to mg/dL
    if glucose.unit and "mmol" in glucose.unit.lower():
        glucose_mg_dl = glucose.value * 18.0
    else:
        glucose_mg_dl = glucose.value

    if glucose_mg_dl < 200:
        return None  # No correction needed

    correction = 0.016 * (glucose_mg_dl - 100)
    corrected_na = na.value + correction

    return {
        "name": "Corrected Sodium",
        "raw_value": round(na.value, 1),
        "corrected_value": round(corrected_na, 1),
        "formula": "Na + 0.016 × (glucose − 100)",
        "unit": na.unit or "mEq/L",
        "interpretation": (
            f"Hyperglycemia ({glucose_mg_dl:.0f} mg/dL) draws water out of cells, "
            f"diluting sodium. Corrected Na ({corrected_na:.1f}) reflects true sodium status."
        ),
    }
