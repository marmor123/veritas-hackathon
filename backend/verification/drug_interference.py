"""
Drug interference detection — flags lab results affected by patient's medications/supplements.

This is the project's "lying supplement" feature: biotin causes false thyroid results,
metformin lowers B12, statins elevate liver enzymes, etc. Catching this BEFORE clinical
interpretation prevents misdiagnosis.

Demo Scenario C: Abnormal TSH + biotin → flag interference, don't interpret as thyroid disease.
"""

from typing import Optional
from backend.api.models.schemas import BiomarkerResult, DrugInterference


# ── Drug interference lookup table ──────────────────────────────────────

DRUG_INTERFERENCE_TABLE: list[dict] = [
    {
        "drug": "Biotin",
        "aliases": ["biotin", "vitamin b7", "vitamin h", "hair skin nails"],
        "type": "supplement",
        "affects": ["TSH", "Free T3", "Free T4", "Troponin", "T3", "T4"],
        "effect": "falsely_lowers",
        "mechanism": "Interferes with biotin-streptavidin immunoassay reagents",
        "recommendation": "Stop biotin for 72 hours before retesting thyroid panel",
    },
    {
        "drug": "Metformin",
        "aliases": ["metformin", "glucophage"],
        "type": "medication",
        "affects": ["Vitamin B12", "B12"],
        "effect": "lowers",
        "mechanism": "Reduces B12 absorption in the ileum over long-term use",
        "recommendation": "Monitor B12 levels yearly; consider supplementation if low",
    },
    {
        "drug": "Statins",
        "aliases": ["statin", "atorvastatin", "rosuvastatin", "simvastatin",
                    "pravastatin", "lovastatin", "lipitor", "crestor"],
        "type": "medication",
        "affects": ["AST", "ALT", "CK", "Creatine Kinase"],
        "effect": "elevates",
        "mechanism": "HMG-CoA reductase inhibition can cause myocyte enzyme leak",
        "recommendation": "If CK > 5x upper limit or LFTs > 3x upper limit, discuss with prescriber",
    },
    {
        "drug": "PPIs",
        "aliases": ["ppi", "omeprazole", "esomeprazole", "lansoprazole",
                    "pantoprazole", "rabeprazole", "nexium", "prilosec"],
        "type": "medication",
        "affects": ["Magnesium", "Vitamin B12", "B12"],
        "effect": "lowers",
        "mechanism": "Reduced gastric acid impairs absorption of magnesium and B12",
        "recommendation": "Consider monitoring magnesium on long-term PPI therapy",
    },
    {
        "drug": "Oral Contraceptives",
        "aliases": ["oral contraceptive", "birth control", "ocp", "estrogen",
                    "ethinyl estradiol"],
        "type": "medication",
        "affects": ["TSH", "T4", "TBG", "Iron", "Transferrin", "Cortisol"],
        "effect": "alters",
        "mechanism": "Estrogen increases thyroid-binding globulin and alters iron metabolism",
        "recommendation": "Interpret thyroid and iron results in context of OC use",
    },
    {
        "drug": "NSAIDs",
        "aliases": ["nsaid", "ibuprofen", "naproxen", "advil", "motrin",
                    "aleve", "diclofenac"],
        "type": "medication",
        "affects": ["Creatinine", "BUN", "eGFR"],
        "effect": "elevates",
        "mechanism": "Reversible reduction in renal blood flow",
        "recommendation": "Recheck renal function after stopping NSAIDs if elevated",
    },
    {
        "drug": "Levothyroxine",
        "aliases": ["levothyroxine", "synthroid", "levoxyl", "thyroxine"],
        "type": "medication",
        "affects": ["TSH", "Free T4", "T4"],
        "effect": "timing_dependent",
        "mechanism": "TSH suppressed shortly after dose; T4 spikes 2-4 hours post-dose",
        "recommendation": "Draw blood BEFORE morning dose for accurate TSH measurement",
    },
    {
        "drug": "ACE Inhibitors",
        "aliases": ["ace inhibitor", "lisinopril", "enalapril", "ramipril",
                    "captopril", "perindopril"],
        "type": "medication",
        "affects": ["Potassium", "Creatinine"],
        "effect": "elevates",
        "mechanism": "Reduced aldosterone causes potassium retention; reduced GFR raises creatinine",
        "recommendation": "Expected effect; monitor potassium and creatinine regularly",
    },
    {
        "drug": "Thiazide Diuretics",
        "aliases": ["thiazide", "hctz", "hydrochlorothiazide", "chlorthalidone"],
        "type": "medication",
        "affects": ["Sodium", "Potassium", "Uric Acid", "Calcium", "Glucose"],
        "effect": "varies",
        "mechanism": "Reduces K+/Na+, elevates Ca/uric acid; can worsen glycemic control",
        "recommendation": "These changes are expected; interpret accordingly",
    },
    {
        "drug": "Creatine Supplement",
        "aliases": ["creatine", "creatine monohydrate"],
        "type": "supplement",
        "affects": ["Creatinine"],
        "effect": "elevates",
        "mechanism": "Creatine is metabolized to creatinine, falsely raising values",
        "recommendation": "Elevated creatinine may not indicate kidney dysfunction; consider cystatin C",
    },
    {
        "drug": "Iron Supplement",
        "aliases": ["iron supplement", "ferrous sulfate", "ferrous gluconate", "iron pill"],
        "type": "supplement",
        "affects": ["Iron", "Ferritin", "Transferrin Saturation"],
        "effect": "elevates",
        "mechanism": "Direct supplementation raises iron stores and serum iron",
        "recommendation": "Hold iron supplements for 24h before iron studies",
    },
    {
        "drug": "Vitamin B12 Supplement",
        "aliases": ["b12 supplement", "cyanocobalamin", "methylcobalamin"],
        "type": "supplement",
        "affects": ["Vitamin B12", "B12", "Methylmalonic Acid"],
        "effect": "elevates",
        "mechanism": "Direct supplementation raises B12 levels",
        "recommendation": "B12 levels reflect supplementation, not endogenous status",
    },
]


def _normalize(text: str) -> str:
    return text.lower().strip()


def _drug_matches(med_name: str, drug_entry: dict) -> bool:
    """Check if a medication name matches a drug entry (any alias)."""
    med_lower = _normalize(med_name)
    aliases = [_normalize(a) for a in drug_entry.get("aliases", [])]
    aliases.append(_normalize(drug_entry["drug"]))
    return any(alias in med_lower or med_lower in alias for alias in aliases)


def _biomarker_affected(biomarker_name: str, affects_list: list[str]) -> bool:
    """Check if a biomarker is in the drug's affected list."""
    name_lower = _normalize(biomarker_name)
    for affected in affects_list:
        affected_lower = _normalize(affected)
        if name_lower == affected_lower or affected_lower in name_lower:
            return True
    return False


def detect_drug_interferences(
    biomarkers: list[BiomarkerResult],
    medications: list[str] | None = None,
) -> list[DrugInterference]:
    """
    Detect drug-lab interferences.

    Args:
        biomarkers: List of biomarker results from OCR
        medications: List of medication/supplement names from user input

    Returns:
        List of DrugInterference objects (only for abnormal biomarkers affected by drugs)
    """
    if not medications:
        return []

    interferences = []
    seen = set()  # avoid duplicates

    for med in medications:
        if not med or not med.strip():
            continue

        for drug_entry in DRUG_INTERFERENCE_TABLE:
            if not _drug_matches(med, drug_entry):
                continue

            # For each affected biomarker, check if it's present and abnormal
            for biomarker in biomarkers:
                if not _biomarker_affected(biomarker.name, drug_entry["affects"]):
                    continue

                # Only flag if the biomarker is actually abnormal
                # (drug effects on normal results aren't actionable)
                is_abnormal = _is_abnormal(biomarker)
                if not is_abnormal:
                    continue

                key = (drug_entry["drug"], biomarker.name)
                if key in seen:
                    continue
                seen.add(key)

                interferences.append(DrugInterference(
                    biomarker=biomarker.name,
                    drug=drug_entry["drug"],
                    effect=drug_entry["effect"].replace("_", " "),
                    recommendation=drug_entry["recommendation"],
                ))

    return interferences


def _is_abnormal(biomarker: BiomarkerResult) -> bool:
    """Check if a biomarker value is outside its reference range."""
    if biomarker.flag and biomarker.flag.lower() in ("h", "l", "high", "low"):
        return True
    if biomarker.ref_low is not None and biomarker.value < biomarker.ref_low:
        return True
    if biomarker.ref_high is not None and biomarker.value > biomarker.ref_high:
        return True
    return False
