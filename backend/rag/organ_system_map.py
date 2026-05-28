"""
Biomarker → Organ System mapping for metadata pre-filtering.

Multi-label: a biomarker can belong to multiple organ systems.
E.g., albumin is both hepatic AND nutritional.
Used by Stage 2 (metadata-filtered hybrid search) to eliminate irrelevant chunks.
"""

# Maps normalized biomarker names to their organ system(s)
ORGAN_SYSTEM_MAP: dict[str, list[str]] = {
    # Hematologic
    "ferritin": ["hematologic"],
    "hemoglobin": ["hematologic"],
    "hgb": ["hematologic"],
    "mcv": ["hematologic"],
    "mch": ["hematologic"],
    "mchc": ["hematologic"],
    "iron": ["hematologic"],
    "serum iron": ["hematologic"],
    "transferrin": ["hematologic"],
    "transferrin saturation": ["hematologic"],
    "tibc": ["hematologic"],
    "platelets": ["hematologic"],
    "wbc": ["hematologic", "inflammatory"],
    "rbc": ["hematologic"],
    "hematocrit": ["hematologic"],
    "hct": ["hematologic"],
    "rdw": ["hematologic"],
    "reticulocyte": ["hematologic"],
    "reticulocyte count": ["hematologic"],
    "neutrophils": ["hematologic", "inflammatory"],
    "lymphocytes": ["hematologic"],
    "monocytes": ["hematologic"],
    "eosinophils": ["hematologic"],
    "basophils": ["hematologic"],
    "haptoglobin": ["hematologic"],
    "fibrinogen": ["hematologic"],
    "pt": ["hematologic"],
    "ptt": ["hematologic"],
    "inr": ["hematologic"],
    "d-dimer": ["hematologic"],

    # Hepatic
    "alt": ["hepatic"],
    "ast": ["hepatic", "musculoskeletal"],
    "ggt": ["hepatic"],
    "alp": ["hepatic"],
    "alkaline phosphatase": ["hepatic"],
    "bilirubin": ["hepatic"],
    "total bilirubin": ["hepatic"],
    "direct bilirubin": ["hepatic"],
    "indirect bilirubin": ["hepatic"],
    "albumin": ["hepatic", "nutritional"],
    "total protein": ["hepatic", "nutritional"],
    "ammonia": ["hepatic"],

    # Renal
    "creatinine": ["renal"],
    "bun": ["renal"],
    "egfr": ["renal"],
    "gfr": ["renal"],
    "cystatin c": ["renal"],
    "uric acid": ["renal", "metabolic"],
    "microalbumin": ["renal"],

    # Thyroid
    "tsh": ["thyroid"],
    "t3": ["thyroid"],
    "t4": ["thyroid"],
    "free t3": ["thyroid"],
    "ft3": ["thyroid"],
    "free t4": ["thyroid"],
    "ft4": ["thyroid"],
    "thyroglobulin": ["thyroid"],
    "tpo": ["thyroid"],
    "reverse t3": ["thyroid"],

    # Metabolic / Cardiovascular
    "glucose": ["metabolic", "cardiometabolic"],
    "hba1c": ["metabolic", "cardiometabolic"],
    "a1c": ["metabolic", "cardiometabolic"],
    "insulin": ["metabolic", "cardiometabolic"],
    "c-peptide": ["metabolic", "cardiometabolic"],
    "cholesterol": ["cardiovascular", "metabolic", "cardiometabolic"],
    "total cholesterol": ["cardiovascular", "metabolic", "cardiometabolic"],
    "ldl": ["cardiovascular", "cardiac"],
    "hdl": ["cardiovascular", "metabolic", "cardiometabolic"],
    "triglycerides": ["metabolic", "cardiovascular", "cardiometabolic"],
    "vldl": ["cardiovascular", "cardiac"],
    "non-hdl": ["cardiovascular", "cardiac"],
    "apob": ["cardiovascular", "cardiac"],
    "lipoprotein(a)": ["cardiovascular", "cardiac"],
    "homocysteine": ["cardiovascular", "cardiac"],

    # Electrolyte
    "sodium": ["electrolyte"],
    "potassium": ["electrolyte"],
    "chloride": ["electrolyte"],
    "co2": ["electrolyte"],
    "bicarbonate": ["electrolyte"],
    "calcium": ["electrolyte", "nutritional"],
    "corrected calcium": ["electrolyte"],
    "magnesium": ["electrolyte", "nutritional"],
    "phosphorus": ["electrolyte"],
    "phosphate": ["electrolyte"],

    # Inflammatory
    "crp": ["inflammatory"],
    "esr": ["inflammatory", "hematologic"],

    # Nutritional
    "vitamin d": ["nutritional"],
    "25-oh vitamin d": ["nutritional"],
    "vitamin b12": ["nutritional"],
    "b12": ["nutritional"],
    "folate": ["nutritional"],
    "zinc": ["nutritional"],
    "selenium": ["nutritional"],
    "copper": ["nutritional"],

    # Cardiac
    "troponin": ["cardiac"],
    "ck": ["musculoskeletal", "cardiac"],
    "ck-mb": ["cardiac"],
    "bnp": ["cardiac"],
    "nt-probnp": ["cardiac"],
    "ldh": ["musculoskeletal", "hematologic"],

    # Endocrine
    "cortisol": ["endocrine"],
    "acth": ["endocrine"],
    "aldosterone": ["endocrine"],
    "testosterone": ["endocrine"],
    "free testosterone": ["endocrine"],
    "estradiol": ["endocrine"],
    "progesterone": ["endocrine"],
    "lh": ["endocrine"],
    "fsh": ["endocrine"],
    "prolactin": ["endocrine"],
    "dhea-s": ["endocrine"],
    "pth": ["endocrine", "electrolyte"],
    "parathyroid hormone": ["endocrine", "electrolyte"],
    "igf-1": ["endocrine"],

    # Pancreatic
    "amylase": ["pancreatic"],
    "lipase": ["pancreatic"],
}


def get_organ_systems_for_biomarkers(biomarker_names: list[str]) -> list[str]:
    """
    Given a list of abnormal biomarker names, return all relevant organ systems.
    Always includes 'hematologic' and 'metabolic' as fallback.
    """
    systems = set()
    for name in biomarker_names:
        normalized = name.lower().strip()
        if normalized in ORGAN_SYSTEM_MAP:
            systems.update(ORGAN_SYSTEM_MAP[normalized])
    # Fallback: always include these broad systems
    systems.add("hematologic")
    systems.add("metabolic")
    return list(systems)


def normalize_biomarker_name(name: str) -> str:
    """Normalize a biomarker name for lookup."""
    return name.lower().strip().replace("_", " ")
