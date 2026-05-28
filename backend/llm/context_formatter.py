"""
Module 5: Context Formatter

Formats all input data (biomarkers, medications, wearable, verification)
into strings that fill the prompt template.

Handles:
- Formatting abnormal biomarkers as a readable table
- Summarizing wearable data
- Formatting verification flags and drug interferences
- Formatting corrected values
"""

from backend.api.models.schemas import (
    VerifiedResult,
    VerificationOutput,
    WearableData,
)


def format_biomarker_table(verified_results: list[VerifiedResult]) -> str:
    """
    Format only abnormal biomarkers into a readable table for the prompt.
    Normal biomarkers are skipped to save context space.
    """
    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        return "All biomarkers are within normal reference ranges."

    lines = []
    for r in abnormal:
        direction = "Low" if r.ref_low is not None and r.value < r.ref_low else "High"
        ref_range = ""
        if r.ref_low is not None and r.ref_high is not None:
            ref_range = f" (ref: {r.ref_low}-{r.ref_high})"
        elif r.ref_low is not None:
            ref_range = f" (ref: >{r.ref_low})"
        elif r.ref_high is not None:
            ref_range = f" (ref: <{r.ref_high})"

        lines.append(f"- {r.biomarker}: {r.value} {r.unit} [{direction}]{ref_range}")

    return "\n".join(lines)


def format_medications(medications: list[str] | None) -> str:
    """Format medication list for the prompt."""
    if not medications:
        return "None reported."
    return ", ".join(medications)


def format_wearable_summary(wearable_data: dict | WearableData | None) -> str:
    """
    Format wearable data into a concise summary string.
    Only includes available data points.
    """
    if not wearable_data:
        return "No wearable data connected."

    # Handle both dict and WearableData object
    if isinstance(wearable_data, WearableData):
        data = wearable_data.model_dump()
    else:
        data = wearable_data

    parts = []

    hr_avg = data.get("resting_hr_avg")
    hr_trend = data.get("resting_hr_trend")
    if hr_avg:
        hr_str = f"Resting HR: {hr_avg} bpm"
        if hr_trend:
            hr_str += f" ({hr_trend})"
        parts.append(hr_str)

    hrv_avg = data.get("hrv_avg")
    hrv_trend = data.get("hrv_trend")
    if hrv_avg:
        hrv_str = f"HRV: {hrv_avg} ms"
        if hrv_trend:
            hrv_str += f" ({hrv_trend})"
        parts.append(hrv_str)

    sleep = data.get("sleep_avg_hours")
    sleep_quality = data.get("sleep_quality")
    if sleep:
        sleep_str = f"Sleep: {sleep}h avg"
        if sleep_quality:
            sleep_str += f" ({sleep_quality})"
        parts.append(sleep_str)

    steps = data.get("activity_avg_steps")
    if steps:
        parts.append(f"Steps: {int(steps)} avg/day")

    if not parts:
        return "No wearable data connected."

    return "; ".join(parts)


def format_verification_flags(verification: VerificationOutput | None) -> str:
    """Format quality flags from verification layer."""
    if not verification or not verification.quality_flags:
        return "None — results appear reliable."

    lines = []
    for flag in verification.quality_flags:
        lines.append(f"- [{flag.type.upper()}] {flag.detail}")
    return "\n".join(lines)


def format_drug_interferences(verification: VerificationOutput | None) -> str:
    """Format detected drug interferences."""
    if not verification or not verification.drug_interferences:
        return "None detected."

    lines = []
    for di in verification.drug_interferences:
        lines.append(
            f"- {di.drug} → {di.biomarker}: {di.effect}. "
            f"Recommendation: {di.recommendation}"
        )
    return "\n".join(lines)


def format_corrected_values(verification: VerificationOutput | None) -> str:
    """Format corrected/derived values."""
    if not verification or not verification.corrected_values:
        return "None applicable."

    lines = []
    for cv in verification.corrected_values:
        name = cv.get("name", "Unknown")
        corrected = cv.get("corrected_value")
        formula = cv.get("formula", "")
        unit = cv.get("unit", "")
        if corrected is not None:
            lines.append(f"- {name}: {corrected} {unit} ({formula})")
    return "\n".join(lines) if lines else "None applicable."
