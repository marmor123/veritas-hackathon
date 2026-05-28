"""
Stage 1: Query Rewriting (LLM Pass 1)

Transforms raw biomarker lists into retrieval-optimized clinical queries.
Raw biomarker lists make poor retrieval queries — clinical textbooks describe
patterns with diagnostic framing, not bare lists.

Latency target: < 3 seconds.
"""

import ollama
from backend.api.models.schemas import VerifiedResult


SYSTEM_PROMPT = """You are a clinical query generator. Transform abnormal lab results \
into a retrieval-optimized clinical search query. Include:
1. The most likely pattern name
2. Severity descriptors for each abnormal biomarker
3. 2-3 differential diagnoses to search for

Output ONLY the query string — no JSON, no explanation, no markdown."""


def format_abnormal_biomarkers(verified_results: list[VerifiedResult]) -> str:
    """Format abnormal biomarkers into a readable string for the LLM."""
    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        return ""

    parts = []
    for r in abnormal:
        direction = "low" if r.flag_reason and "low" in r.flag_reason.lower() else "high"
        if r.value < (r.ref_low or 0):
            direction = "low"
        elif r.value > (r.ref_high or float("inf")):
            direction = "high"
        parts.append(f"{r.biomarker} {r.value} {r.unit} ({direction})")

    return ", ".join(parts)


def rewrite_query(
    verified_results: list[VerifiedResult],
    medications: list[str] | None = None,
    model: str = "qvac-medpsy:1.7b",
    timeout: float = 10.0,
) -> str:
    """
    Rewrite abnormal biomarkers into a clinical retrieval query.

    Args:
        verified_results: List of verified biomarker results
        medications: Optional list of medication names
        model: Ollama model to use
        timeout: Timeout in seconds

    Returns:
        A clinically-framed retrieval query string.
        Falls back to a simple formatted query if LLM is unavailable.
    """
    abnormal_str = format_abnormal_biomarkers(verified_results)
    if not abnormal_str:
        return ""

    meds_str = ", ".join(medications) if medications else "None reported"

    user_prompt = (
        f"Abnormal biomarkers: {abnormal_str}\n"
        f"Patient medications: {meds_str}\n"
        f"Generate a clinical retrieval query."
    )

    try:
        response = ollama.generate(
            model=model,
            system=SYSTEM_PROMPT,
            prompt=user_prompt,
            options={
                "temperature": 0.3,
                "num_predict": 256,
            },
        )
        rewritten = response.get("response", "").strip()
        if rewritten and len(rewritten) > 20:
            return rewritten
    except Exception as e:
        print(f"[QueryRewriter] LLM call failed: {e}. Using fallback.")

    # Fallback: construct a basic clinical query from the biomarker list
    return _fallback_query(verified_results)


def _fallback_query(verified_results: list[VerifiedResult]) -> str:
    """
    Construct a basic clinical query without LLM.
    Groups biomarkers by direction and adds pattern-matching keywords.
    """
    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        return ""

    low_markers = []
    high_markers = []

    for r in abnormal:
        if r.ref_low is not None and r.value < r.ref_low:
            low_markers.append(f"{r.biomarker} {r.value} {r.unit}")
        elif r.ref_high is not None and r.value > r.ref_high:
            high_markers.append(f"{r.biomarker} {r.value} {r.unit}")

    parts = []
    if low_markers:
        parts.append(f"Low values: {', '.join(low_markers)}.")
    if high_markers:
        parts.append(f"Elevated values: {', '.join(high_markers)}.")

    # Add pattern-matching keywords based on biomarker combinations
    marker_names = {r.biomarker.lower() for r in abnormal}

    # Iron deficiency pattern
    if {"ferritin", "mcv", "hemoglobin"} & marker_names or {"ferritin", "iron"} & marker_names:
        parts.append("Iron deficiency anemia microcytic anemia pattern.")

    # Metabolic syndrome pattern
    if len({"glucose", "hdl", "triglycerides", "alt", "uric acid"} & marker_names) >= 3:
        parts.append("Metabolic syndrome insulin resistance dyslipidemia pattern.")

    # Thyroid pattern
    if {"tsh"} & marker_names:
        parts.append("Thyroid dysfunction hypothyroidism hyperthyroidism pattern.")

    # B12/folate deficiency
    if {"vitamin b12", "b12", "folate"} & marker_names:
        parts.append("Vitamin B12 deficiency macrocytic anemia pattern.")

    # Kidney pattern
    if {"creatinine", "egfr", "bun"} & marker_names:
        parts.append("Renal dysfunction kidney disease pattern.")

    parts.append("Clinical pattern identification and differential diagnosis.")
    return " ".join(parts)
