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
    Construct a clinical retrieval query without LLM.

    The cross-encoder (ms-marco-MiniLM) was trained on natural-language
    question-passage pairs, so we generate a question-shaped query
    (not a raw value list) for better re-ranking.

    Strategy:
      1. Detect the dominant pattern from biomarker combinations
      2. Build a single focused clinical question (not multiple patterns)
      3. Avoid mixing contradictory keywords (e.g., hyperthyroid + hypothyroid)
    """
    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        return ""

    # Categorize abnormal biomarkers by direction
    low_markers = []
    high_markers = []
    for r in abnormal:
        if r.ref_low is not None and r.value < r.ref_low:
            low_markers.append((r.biomarker.lower(), r.value, r.unit))
        elif r.ref_high is not None and r.value > r.ref_high:
            high_markers.append((r.biomarker.lower(), r.value, r.unit))

    marker_names = {r.biomarker.lower() for r in abnormal}

    # ── Detect the SINGLE most likely pattern ──
    # Order matters: more specific patterns first
    pattern_query = None

    # Iron deficiency: low ferritin + low MCV is the diagnostic combo
    if {"ferritin"} & marker_names and any(
        m in marker_names for m in ["mcv", "hemoglobin", "iron"]
    ):
        pattern_query = (
            "What is the differential diagnosis for microcytic anemia with "
            "low ferritin, low MCV, and low hemoglobin? Iron deficiency anemia "
            "vs anemia of chronic disease vs thalassemia trait."
        )

    # B12/Folate deficiency: macrocytic anemia
    elif (any(m in marker_names for m in ["vitamin b12", "b12", "folate"])
          and "mcv" in marker_names):
        pattern_query = (
            "What is the differential diagnosis for macrocytic anemia with "
            "low vitamin B12 or folate and elevated MCV? B12 deficiency, "
            "folate deficiency, megaloblastic anemia."
        )

    # Hypothyroidism: high TSH + low FT4
    elif "tsh" in marker_names:
        # Determine direction
        tsh_high = any(b == "tsh" for b, _, _ in high_markers)
        ft4_low = any(b in ("free t4", "ft4") for b, _, _ in low_markers)

        if tsh_high and ft4_low:
            pattern_query = (
                "What are the laboratory findings in primary hypothyroidism "
                "with elevated TSH and low Free T4?"
            )
        elif tsh_high:
            pattern_query = (
                "What is the differential diagnosis for elevated TSH? "
                "Subclinical hypothyroidism, primary hypothyroidism."
            )
        else:
            pattern_query = (
                "What is the differential diagnosis for suppressed TSH? "
                "Hyperthyroidism, thyroid hormone use, central hypothyroidism."
            )

    # Metabolic syndrome: glucose + lipids combo
    elif (len({"glucose", "hdl", "triglycerides", "alt", "uric acid"} & marker_names) >= 3):
        pattern_query = (
            "What are the laboratory findings in metabolic syndrome and "
            "insulin resistance with elevated glucose, low HDL, elevated "
            "triglycerides, and elevated liver enzymes?"
        )

    # Kidney dysfunction: creatinine/eGFR/BUN
    elif any(m in marker_names for m in ["creatinine", "egfr", "bun"]):
        pattern_query = (
            "What is the differential diagnosis for acute kidney injury and "
            "chronic kidney disease with elevated creatinine, elevated BUN, "
            "and reduced eGFR?"
        )

    # Liver dysfunction: ALT/AST/ALP/Bilirubin
    elif any(m in marker_names for m in ["alt", "ast", "alp", "bilirubin"]):
        pattern_query = (
            "What is the differential diagnosis for elevated liver enzymes "
            "with hepatocellular vs cholestatic patterns of injury?"
        )

    # Hemolysis / hyperkalemia
    elif "potassium" in marker_names and any(
        b == "potassium" for b, _, _ in high_markers
    ):
        pattern_query = (
            "What is the differential diagnosis for hyperkalemia? "
            "Pseudohyperkalemia from hemolysis, kidney disease, "
            "medication effects."
        )

    # Generic fallback if no pattern detected
    if pattern_query is None:
        pattern_query = (
            f"What is the differential diagnosis for "
            f"abnormal laboratory findings including "
            f"{', '.join(b for b, _, _ in (low_markers + high_markers)[:5])}?"
        )

    # Append the actual values for context (helps semantic search match
    # specific magnitudes)
    value_str_parts = []
    for b, v, u in low_markers:
        value_str_parts.append(f"{b} {v} {u} (low)")
    for b, v, u in high_markers:
        value_str_parts.append(f"{b} {v} {u} (high)")

    return f"{pattern_query} Values: {', '.join(value_str_parts)}."
