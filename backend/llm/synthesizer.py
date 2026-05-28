"""
Module 5: LLM Synthesizer

The main orchestrator:
1. Assembles the full prompt from all inputs
2. Calls Ollama with the local LLM
3. Parses the JSON response
4. Falls back to demo outputs if LLM is unavailable

This is the single entry point for Module 5.
"""

import json
import logging

logger = logging.getLogger(__name__)

from backend.api.models.schemas import (
    AnalysisOutput,
    PatternResult,
    VerifiedResult,
    VerificationOutput,
    Severity,
    Confidence,
)
from backend.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from backend.llm.context_formatter import (
    format_biomarker_table,
    format_medications,
    format_wearable_summary,
    format_verification_flags,
    format_drug_interferences,
    format_corrected_values,
)
from backend.llm.demo_outputs import get_demo_output, match_demo_scenario


# Default model — can be overridden
DEFAULT_MODEL = "qwen3.5:0.8b"
FALLBACK_MODELS = ["qwen3:1.7b", "qwen3:4b", "llama3.2:1b"]

DISCLAIMER = (
    "This is not a medical diagnosis. All identified patterns should be "
    "discussed with a qualified healthcare provider."
)


def synthesize(
    verified_results: list[VerifiedResult],
    citations_formatted: str,
    verification: VerificationOutput | None = None,
    medications: list[str] | None = None,
    wearable_data: dict | None = None,
    model: str | None = None,
    use_demo_fallback: bool = True,
) -> AnalysisOutput:
    """
    Run LLM synthesis to produce the final AnalysisOutput.

    Args:
        verified_results: Verified biomarker results (from Module 3)
        citations_formatted: Formatted citation string (from Module 4)
        verification: Full verification output (flags, interferences, corrected values)
        medications: Patient medication list
        wearable_data: Wearable data dict
        model: Ollama model name (defaults to DEFAULT_MODEL)
        use_demo_fallback: If True, fall back to demo outputs when LLM fails

    Returns:
        AnalysisOutput ready for the frontend.
    """
    # Fast path: all normal
    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        logger.info("[Synthesizer] All biomarkers normal — skipping LLM")
        return _all_normal_output(verification)

    logger.info("[Synthesizer] %d abnormal biomarkers found, proceeding with LLM synthesis", len(abnormal))

    # Build the full prompt
    prompt = _build_prompt(
        verified_results=verified_results,
        citations_formatted=citations_formatted,
        verification=verification,
        medications=medications,
        wearable_data=wearable_data,
    )
    logger.info("[Synthesizer] Prompt built (%d chars)", len(prompt))

    # Try LLM call
    model_to_use = model or DEFAULT_MODEL
    logger.info("[Synthesizer] Trying primary model: %s", model_to_use)
    result = _call_llm(prompt, model_to_use)

    if result is not None:
        logger.info("[Synthesizer] SUCCESS with model %s", model_to_use)
        return result

    # LLM failed — try fallback models
    for fallback_model in FALLBACK_MODELS:
        if fallback_model == model_to_use:
            continue
        logger.info("[Synthesizer] Trying fallback model: %s", fallback_model)
        result = _call_llm(prompt, fallback_model)
        if result is not None:
            logger.info("[Synthesizer] SUCCESS with fallback model %s", fallback_model)
            return result

    # All LLM attempts failed — use demo fallback
    logger.warning("[Synthesizer] All LLM models failed. Trying demo fallback...")
    if use_demo_fallback:
        demo = match_demo_scenario(verified_results)
        if demo:
            logger.info("[Synthesizer] Matched demo scenario as fallback")
            return demo

    # Ultimate fallback: return raw findings without LLM interpretation
    logger.warning("[Synthesizer] Returning raw fallback output (no LLM, no demo match)")
    return _raw_fallback_output(verified_results, verification)


def _build_prompt(
    verified_results: list[VerifiedResult],
    citations_formatted: str,
    verification: VerificationOutput | None,
    medications: list[str] | None,
    wearable_data: dict | None,
) -> str:
    """Assemble the user prompt from all data sources."""
    return USER_PROMPT_TEMPLATE.format(
        biomarker_table=format_biomarker_table(verified_results),
        medications=format_medications(medications),
        wearable_summary=format_wearable_summary(wearable_data),
        verification_flags=format_verification_flags(verification),
        drug_interferences=format_drug_interferences(verification),
        corrected_values=format_corrected_values(verification),
        citations_formatted=citations_formatted or "No relevant clinical knowledge retrieved.",
    )


def _call_llm(prompt: str, model: str) -> AnalysisOutput | None:
    """
    Call Ollama and parse the response as AnalysisOutput.
    Returns None if the call fails or output can't be parsed.
    """
    try:
        import ollama

        logger.info("[Synthesizer] Calling ollama.generate(model=%s)...", model)
        response = ollama.generate(
            model=model,
            system=SYSTEM_PROMPT,
            prompt=prompt,
            format="json",
            think=False,  # Disable thinking mode for Qwen3.5 models
            options={
                "temperature": 0.3,
                "num_predict": 2048,
            },
        )
        raw_text = response.get("response", "").strip()
        if not raw_text:
            logger.warning("[Synthesizer] Empty response from %s", model)
            return None

        logger.info("[Synthesizer] Got response from %s (%d chars), parsing...", model, len(raw_text))
        return _parse_llm_output(raw_text)

    except ImportError:
        logger.error("[Synthesizer] 'ollama' package not installed!")
        return None
    except Exception as e:
        logger.error("[Synthesizer] LLM call failed (%s): %s", model, e)
        return None


def _parse_llm_output(raw_text: str) -> AnalysisOutput | None:
    """
    Parse LLM JSON output into AnalysisOutput.
    Handles common LLM quirks (extra text around JSON, missing fields).
    """
    # Try to extract JSON from the response (LLM might add text around it)
    json_str = _extract_json(raw_text)
    if not json_str:
        logger.warning("[Synthesizer] Could not extract JSON from response: %s", raw_text[:200])
        return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("[Synthesizer] JSON parse error: %s — raw: %s", e, json_str[:200])
        return None

    # Build AnalysisOutput from parsed data
    try:
        patterns = []
        for p in data.get("patterns", []):
            patterns.append(PatternResult(
                name=p.get("name", "Unknown Pattern"),
                severity=_safe_severity(p.get("severity", "ADVISORY")),
                confidence=_safe_confidence(p.get("confidence", "MODERATE")),
                explanation=p.get("explanation", ""),
                symptomatic_note=p.get("symptomatic_note"),
                supporting_markers=p.get("supporting_markers", []),
                citations=p.get("citations", []),
                doctor_questions=p.get("doctor_questions", []),
            ))

        # Sort patterns by severity (WARNING first, then CAUTION, then ADVISORY)
        severity_order = {"WARNING": 0, "CAUTION": 1, "ADVISORY": 2}
        patterns.sort(key=lambda p: severity_order.get(p.severity.value, 3))

        verification_alerts = data.get("verification_alerts", [])

        return AnalysisOutput(
            summary=data.get("summary", "Analysis complete."),
            patterns=patterns,
            verification_alerts=verification_alerts,
            disclaimer=data.get("disclaimer", DISCLAIMER),
        )

    except Exception as e:
        logger.error("[Synthesizer] Error building AnalysisOutput: %s", e)
        return None


def _extract_json(text: str) -> str | None:
    """Extract JSON object from text that might have extra content around it."""
    # Try the whole text first
    text = text.strip()
    if text.startswith("{"):
        return text

    # Try to find JSON between braces
    start = text.find("{")
    if start == -1:
        return None

    # Find matching closing brace
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None


def _safe_severity(value: str) -> Severity:
    """Map a string to Severity enum, defaulting to ADVISORY."""
    try:
        return Severity(value.upper())
    except (ValueError, AttributeError):
        return Severity.ADVISORY


def _safe_confidence(value: str) -> Confidence:
    """Map a string to Confidence enum, defaulting to MODERATE."""
    try:
        return Confidence(value.upper())
    except (ValueError, AttributeError):
        return Confidence.MODERATE


def _all_normal_output(verification: VerificationOutput | None) -> AnalysisOutput:
    """Output when all biomarkers are within normal range."""
    alerts = []
    if verification and verification.quality_flags:
        for flag in verification.quality_flags:
            alerts.append({
                "biomarker": ", ".join(flag.affected_biomarkers),
                "issue": flag.detail,
                "recommendation": "Discuss with your healthcare provider.",
            })

    return AnalysisOutput(
        summary="All biomarker results are within normal reference ranges. No clinical patterns detected.",
        patterns=[],
        verification_alerts=alerts,
        disclaimer=DISCLAIMER,
    )


def _raw_fallback_output(
    verified_results: list[VerifiedResult],
    verification: VerificationOutput | None,
) -> AnalysisOutput:
    """
    Fallback when LLM is completely unavailable.
    Returns abnormal biomarkers as individual findings without pattern grouping.
    """
    abnormal = [r for r in verified_results if r.flagged]

    markers = []
    for r in abnormal:
        direction = "Low" if r.ref_low and r.value < r.ref_low else "High"
        markers.append(f"{r.biomarker}: {r.value} {r.unit} ({direction})")

    alerts = []
    if verification:
        for flag in verification.quality_flags:
            alerts.append({
                "biomarker": ", ".join(flag.affected_biomarkers),
                "issue": flag.detail,
                "recommendation": "Discuss with your healthcare provider.",
            })
        for di in verification.drug_interferences:
            alerts.append({
                "biomarker": di.biomarker,
                "issue": f"Possible {di.effect} due to {di.drug}",
                "recommendation": di.recommendation,
            })

    pattern = PatternResult(
        name="Abnormal Results (analysis unavailable)",
        severity=Severity.ADVISORY,
        confidence=Confidence.LOW,
        explanation=(
            "The AI analysis engine is currently unavailable. "
            "The following biomarkers are outside their reference ranges. "
            "Please discuss these results with your healthcare provider."
        ),
        symptomatic_note=None,
        supporting_markers=markers,
        citations=[],
        doctor_questions=[
            "Which of these abnormal values are most clinically significant?",
            "Should any of these be retested or investigated further?",
        ],
    )

    return AnalysisOutput(
        summary=f"{len(abnormal)} biomarker(s) outside reference range. AI analysis unavailable — showing raw findings.",
        patterns=[pattern] if abnormal else [],
        verification_alerts=alerts,
        disclaimer=DISCLAIMER,
    )
