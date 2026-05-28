"""
Module 5: Pre-cached Demo Outputs

These are ready-made AnalysisOutput objects for the 4 demo scenarios.
Used when:
  - LLM is unavailable (fallback)
  - Demo mode is activated (instant response, no waiting)
  - Testing the frontend without a running LLM

Each output matches what the LLM would produce for that scenario.
"""

from backend.api.models.schemas import (
    AnalysisOutput,
    PatternResult,
    VerifiedResult,
    Severity,
    Confidence,
)


DISCLAIMER = (
    "This is not a medical diagnosis. All identified patterns should be "
    "discussed with a qualified healthcare provider."
)


# ── Scenario 1: Iron Deficiency + Wearable ──────────────────────────────

DEMO_IRON_DEFICIENCY = AnalysisOutput(
    summary=(
        "Your blood test shows a pattern consistent with iron deficiency. "
        "Four related markers are below normal range, forming a recognizable "
        "clinical pattern. Your smartwatch data suggests your body may already "
        "be compensating with an elevated heart rate."
    ),
    patterns=[
        PatternResult(
            name="Iron Deficiency Pattern",
            severity=Severity.CAUTION,
            confidence=Confidence.HIGH,
            explanation=(
                "Your ferritin (iron stores) is very low at 12 ng/mL, which has led to "
                "smaller red blood cells (low MCV) and mildly reduced hemoglobin. This "
                "combination is the hallmark of iron deficiency anemia. Your rising resting "
                "heart rate (68→76 bpm over 30 days) may indicate your heart is working "
                "harder to deliver oxygen with fewer red blood cells."
            ),
            symptomatic_note=(
                "Your resting heart rate has been trending upward (68→76 bpm), "
                "which may be compensatory tachycardia related to reduced oxygen-carrying capacity."
            ),
            supporting_markers=[
                "Ferritin: 12 ng/mL (Low)",
                "Iron: 35 µg/dL (Low)",
                "MCV: 78 fL (Low)",
                "Hemoglobin: 11.2 g/dL (Low)",
            ],
            citations=[
                "Wallach's Interpretation of Diagnostic Tests, 11th Ed — Hematologic Disorders, Microcytic Anemias",
            ],
            doctor_questions=[
                "My ferritin is 12 ng/mL — what iron supplementation strategy would you recommend, and what formulation?",
                "Should we investigate the cause of my iron deficiency — diet, absorption, or blood loss?",
                "My resting heart rate has trended up from 68 to 76 bpm — is this related to my low hemoglobin?",
            ],
        ),
    ],
    verification_alerts=[],
    disclaimer=DISCLAIMER,
)


# ── Scenario 2: Metabolic Syndrome ──────────────────────────────────────

DEMO_METABOLIC_SYNDROME = AnalysisOutput(
    summary=(
        "Your results show a cluster of five metabolic markers that together suggest "
        "insulin resistance. This is one interconnected pattern, not five separate problems."
    ),
    patterns=[
        PatternResult(
            name="Metabolic Syndrome Pattern",
            severity=Severity.CAUTION,
            confidence=Confidence.HIGH,
            explanation=(
                "Elevated fasting glucose (108 mg/dL), low HDL (34 mg/dL), high triglycerides "
                "(195 mg/dL), borderline elevated ALT (48 U/L suggesting early fatty liver), "
                "and elevated uric acid (7.8 mg/dL) together form the metabolic syndrome pattern. "
                "These are interconnected through insulin resistance — the underlying mechanism "
                "that drives all five abnormalities."
            ),
            symptomatic_note=None,
            supporting_markers=[
                "Glucose: 108 mg/dL (High)",
                "HDL: 34 mg/dL (Low)",
                "Triglycerides: 195 mg/dL (High)",
                "ALT: 48 U/L (High)",
                "Uric Acid: 7.8 mg/dL (High)",
            ],
            citations=[
                "Wallach's Interpretation of Diagnostic Tests, 11th Ed — Endocrine Diseases, Diabetes/Metabolic Syndrome",
            ],
            doctor_questions=[
                "Do these results meet the criteria for metabolic syndrome, and should we measure waist circumference and blood pressure to confirm?",
                "Would lifestyle interventions alone be appropriate, or should we consider medication at this stage?",
                "Should we order HbA1c to assess longer-term glucose control?",
            ],
        ),
    ],
    verification_alerts=[],
    disclaimer=DISCLAIMER,
)


# ── Scenario 3: Biotin Interference ─────────────────────────────────────

DEMO_BIOTIN_INTERFERENCE = AnalysisOutput(
    summary=(
        "Your TSH appears low, but this result may not be trustworthy. "
        "Biotin supplementation is known to interfere with thyroid immunoassays, "
        "producing falsely abnormal TSH values."
    ),
    patterns=[
        PatternResult(
            name="Possible Biotin Interference",
            severity=Severity.ADVISORY,
            confidence=Confidence.HIGH,
            explanation=(
                "Your TSH (0.15 mIU/L) is below normal, but Free T4 (1.3 ng/dL) is "
                "completely normal. In true hyperthyroidism, we would expect elevated Free T4. "
                "This discordance, combined with your biotin supplementation, strongly suggests "
                "biotin interference with the TSH immunoassay rather than actual thyroid disease."
            ),
            symptomatic_note=None,
            supporting_markers=[
                "TSH: 0.15 mIU/L (Low)",
                "Free T4: 1.3 ng/dL (Normal — inconsistent with true hyperthyroidism)",
            ],
            citations=[
                "Wallach's Interpretation of Diagnostic Tests, 11th Ed — Endocrine Diseases, Thyroid Disorders",
            ],
            doctor_questions=[
                "Should I stop biotin for 48-72 hours and repeat the TSH test to confirm this is interference?",
                "Are any of my other test results potentially affected by biotin?",
                "Is there an alternative assay method that is not affected by biotin?",
            ],
        ),
    ],
    verification_alerts=[
        {
            "biomarker": "TSH",
            "issue": "Possible biotin interference — TSH immunoassay uses biotin-streptavidin chemistry that can produce falsely low results",
            "recommendation": "Stop biotin for 72 hours and repeat thyroid panel",
        },
    ],
    disclaimer=DISCLAIMER,
)


# ── Scenario 4: Hemolysis Artifact ──────────────────────────────────────

DEMO_HEMOLYSIS_ARTIFACT = AnalysisOutput(
    summary=(
        "Your potassium appears dangerously high, but this is very likely a sample "
        "collection error (hemolysis), not a true medical emergency. Your kidney "
        "function is completely normal, which makes true hyperkalemia very unlikely."
    ),
    patterns=[
        PatternResult(
            name="Suspected Hemolysis Artifact",
            severity=Severity.WARNING,
            confidence=Confidence.HIGH,
            explanation=(
                "Extremely elevated potassium (6.8 mEq/L) with completely normal kidney "
                "function (eGFR 95, creatinine 0.9) is a classic hemolysis pattern. When red "
                "blood cells rupture during blood draw, they release intracellular potassium "
                "and LDH into the sample. Your elevated LDH (380 U/L) and very low glucose "
                "(45 mg/dL — consumed by lysed cells) further confirm this is a sample quality "
                "issue, not a true electrolyte emergency."
            ),
            symptomatic_note=None,
            supporting_markers=[
                "Potassium: 6.8 mEq/L (High — likely artifact)",
                "LDH: 380 U/L (High — released from lysed RBCs)",
                "Glucose: 45 mg/dL (Low — consumed by lysed cells)",
                "eGFR: 95 mL/min (Normal — rules out true hyperkalemia)",
                "Creatinine: 0.9 mg/dL (Normal)",
            ],
            citations=[
                "Wallach's Interpretation of Diagnostic Tests, 11th Ed — Pre-analytical Errors, Hemolysis",
            ],
            doctor_questions=[
                "Should I have my potassium rechecked with a fresh blood draw to confirm this was hemolysis?",
                "Is there anything about my veins or the draw technique that might have caused this?",
                "Are any other values in this panel potentially affected by the hemolyzed sample?",
            ],
        ),
    ],
    verification_alerts=[
        {
            "biomarker": "Potassium",
            "issue": "Very high K+ (6.8) with normal kidney function (eGFR 95) — classic hemolysis pattern",
            "recommendation": "Recommend repeat blood draw with careful collection technique",
        },
    ],
    disclaimer=DISCLAIMER,
)


# ── Demo scenario registry ──────────────────────────────────────────────

DEMO_SCENARIOS = {
    "iron_deficiency": DEMO_IRON_DEFICIENCY,
    "metabolic_syndrome": DEMO_METABOLIC_SYNDROME,
    "biotin_interference": DEMO_BIOTIN_INTERFERENCE,
    "hemolysis_artifact": DEMO_HEMOLYSIS_ARTIFACT,
}


def get_demo_output(scenario_name: str) -> AnalysisOutput | None:
    """Get a pre-cached demo output by scenario name."""
    return DEMO_SCENARIOS.get(scenario_name)


def match_demo_scenario(verified_results: list[VerifiedResult]) -> AnalysisOutput | None:
    """
    Try to match verified results to a known demo scenario.
    Used as fallback when LLM is unavailable.
    """
    abnormal = {r.biomarker.lower() for r in verified_results if r.flagged}

    # Iron deficiency: ferritin + MCV + hemoglobin
    if {"ferritin", "mcv", "hemoglobin"} & abnormal and len(abnormal) <= 6:
        return DEMO_IRON_DEFICIENCY

    # Metabolic: glucose + HDL + triglycerides
    if {"glucose", "hdl", "triglycerides"} & abnormal and len(abnormal) >= 3:
        return DEMO_METABOLIC_SYNDROME

    # Biotin: TSH low alone (or with normal FT4)
    if "tsh" in abnormal and len(abnormal) <= 2:
        return DEMO_BIOTIN_INTERFERENCE

    # Hemolysis: potassium very high
    if "potassium" in abnormal:
        return DEMO_HEMOLYSIS_ARTIFACT

    return None
