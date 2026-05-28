"""
Stage 1: Query Rewriting (LLM Pass 1)

Transforms raw biomarker lists into retrieval-optimized clinical queries.
Raw biomarker lists make poor retrieval queries — clinical textbooks describe
patterns with diagnostic framing, not bare lists.

Latency target: < 3 seconds.
"""

from backend.api.models.schemas import VerifiedResult


SYSTEM_PROMPT = """You are a clinical retrieval query generator for a RAG system.
Your output will be embedded (all-MiniLM-L6-v2) and used to search a medical
textbook (Wallach's Interpretation of Diagnostic Tests, 11th Edition) via
semantic search + cross-encoder re-ranking.

Given abnormal lab results, produce a single clinical search query that:
- Names the most likely clinical pattern(s) using textbook terminology
  (e.g., "microcytic anemia", "metabolic syndrome", "primary hypothyroidism")
- Describes the direction and magnitude of each abnormal value
- Lists 2-3 differential diagnoses that should also be searched for
- Incorporates relevant medication/supplement context if provided
- Uses natural clinical language, not a bare list of biomarkers
- Is 2-5 sentences, optimized for semantic similarity search

CRITICAL: The cross-encoder (ms-marco-MiniLM) was trained on question-passage
pairs, so phrasing your output as a clinical question or diagnostic framing
will produce much better retrieval than a biomarker list.

Output ONLY the query string — no JSON, no markdown, no "Query:" prefix."""


def format_biomarker_for_prompt(r: VerifiedResult) -> str:
    """Format a single biomarker with value, unit, direction, and reference range."""
    if r.ref_low is not None and r.value < r.ref_low:
        direction = "Low"
    elif r.ref_high is not None and r.value > r.ref_high:
        direction = "High"
    else:
        direction = "Normal"

    ref = ""
    if r.ref_low is not None and r.ref_high is not None:
        ref = f", ref: {r.ref_low}-{r.ref_high}"
    elif r.ref_low is not None:
        ref = f", ref: >{r.ref_low}"
    elif r.ref_high is not None:
        ref = f", ref: <{r.ref_high}"

    return f"- {r.biomarker}: {r.value} {r.unit} [{direction}{ref}]"


def format_abnormal_biomarkers(verified_results: list[VerifiedResult]) -> str:
    """Format all biomarkers: abnormal ones with details, plus key normal ones for context."""
    abnormal = [r for r in verified_results if r.flagged]
    normal = [r for r in verified_results if not r.flagged]

    if not abnormal:
        return "All biomarkers are within normal reference ranges."

    lines = []
    lines.append("ABNORMAL:")
    for r in abnormal:
        lines.append(format_biomarker_for_prompt(r))

    if normal:
        # Include normal biomarkers for clinical context (helps LLM reason about
        # things like "high K+ with normal kidney function = possible artifact")
        lines.append("\nNORMAL (for clinical context):")
        for r in normal:
            lines.append(format_biomarker_for_prompt(r))

    return "\n".join(lines)


def rewrite_query(
    verified_results: list[VerifiedResult],
    medications: list[str] | None = None,
    model: str = "qwen3.5:0.8b",
    timeout: float = 15.0,
) -> str:
    """
    Rewrite abnormal biomarkers into a clinical retrieval query.

    Uses qwen3.5:0.8b via Ollama as the primary path. Falls back to a simple
    formatted query if the LLM is unavailable — the fallback is deliberately
    basic since we invest in the LLM path.

    Args:
        verified_results: List of verified biomarker results
        medications: Optional list of medication names
        model: Ollama model to use (default: qwen3.5:0.8b)
        timeout: Timeout in seconds

    Returns:
        A clinically-framed retrieval query string optimized for
        embedding similarity + cross-encoder re-ranking.
    """
    biomarker_str = format_abnormal_biomarkers(verified_results)
    if not biomarker_str:
        return ""

    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        return ""

    meds_str = ", ".join(medications) if medications else "None reported"

    user_prompt = (
        f"{biomarker_str}\n\n"
        f"Medications/supplements: {meds_str}\n\n"
        f"Generate a clinical retrieval query optimized for searching medical "
        f"textbook chapters. Include the most likely pattern name, differential "
        f"diagnoses, and relevant medication context."
    )

    # ── Primary path: LLM via Ollama ──────────────────────────────────────
    try:
        import ollama
    except ImportError:
        print("[QueryRewriter] ollama package not installed. Using fallback.")
        return _fallback_query(verified_results)

    try:
        response = ollama.generate(
            model=model,
            system=SYSTEM_PROMPT,
            prompt=user_prompt,
            think=False,  # Disable thinking mode (qwen3.5 uses it by default)
            options={
                "temperature": 0.3,
                "num_predict": 512,
            },
        )
        rewritten = response.get("response", "").strip()

        # Strip "Query:" prefix if the LLM adds one
        if rewritten.lower().startswith("query:"):
            rewritten = rewritten[6:].strip()
        if rewritten.lower().startswith("clinical query:"):
            rewritten = rewritten[15:].strip()

        if rewritten and len(rewritten) > 20:
            print(f"[QueryRewriter] LLM query ({len(rewritten)} chars): {rewritten[:150]}...")
            return rewritten

        print("[QueryRewriter] LLM returned empty or too-short response. Using fallback.")
    except Exception as e:
        print(f"[QueryRewriter] LLM call failed ({type(e).__name__}: {e}). Using fallback.")

    # ── Fallback: simple clinical query from biomarker data ────────────────
    return _fallback_query(verified_results)


def _fallback_query(verified_results: list[VerifiedResult]) -> str:
    """
    Simple fallback: format biomarkers into a clinical question without LLM.

    Deliberately basic — our investment is in the LLM path. This fallback
    formats abnormal values into a question-shaped query (the cross-encoder
    was trained on question-passage pairs) with sufficient clinical framing
    to produce reasonable retrieval.
    """
    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        return ""

    low_parts = []
    high_parts = []
    for r in abnormal:
        detail = f"{r.biomarker} {r.value} {r.unit}"
        if r.ref_low is not None and r.value < r.ref_low:
            low_parts.append(detail)
        elif r.ref_high is not None and r.value > r.ref_high:
            high_parts.append(detail)
        else:
            low_parts.append(detail)  # flagged but direction unclear

    conditions = []
    if low_parts:
        conditions.append(f"low values: {', '.join(low_parts)}")
    if high_parts:
        conditions.append(f"elevated values: {', '.join(high_parts)}")

    if not conditions:
        conditions.append(f"abnormal findings: {', '.join(r.biomarker for r in abnormal)}")

    condition_str = "; ".join(conditions)

    return (
        f"What is the differential diagnosis and clinical interpretation for "
        f"the following abnormal laboratory results? {condition_str}. "
        f"Identify relevant patterns, possible causes, and recommended follow-up."
    )
