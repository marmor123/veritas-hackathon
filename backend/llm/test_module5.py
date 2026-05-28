"""
Tests for Module 5: LLM Synthesis

Run with: python -m pytest backend/llm/test_module5.py -v
Or standalone: python backend/llm/test_module5.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.api.models.schemas import (
    AnalysisOutput,
    PatternResult,
    VerifiedResult,
    VerificationOutput,
    QualityFlag,
    DrugInterference,
    Severity,
    Confidence,
)
from backend.llm.demo_outputs import (
    get_demo_output,
    match_demo_scenario,
    DEMO_SCENARIOS,
)
from backend.llm.context_formatter import (
    format_biomarker_table,
    format_medications,
    format_wearable_summary,
    format_verification_flags,
    format_drug_interferences,
    format_corrected_values,
)
from backend.llm.synthesizer import (
    _parse_llm_output,
    _build_prompt,
    _all_normal_output,
    _raw_fallback_output,
    synthesize,
)


# ── Test fixtures ────────────────────────────────────────────────────────

IRON_DEFICIENCY_RESULTS = [
    VerifiedResult(biomarker="Ferritin", value=12, unit="ng/mL", ref_low=15, ref_high=150, flagged=True, flag_reason="Below reference range (15)"),
    VerifiedResult(biomarker="Iron", value=35, unit="µg/dL", ref_low=60, ref_high=170, flagged=True, flag_reason="Below reference range (60)"),
    VerifiedResult(biomarker="MCV", value=78, unit="fL", ref_low=80, ref_high=100, flagged=True, flag_reason="Below reference range (80)"),
    VerifiedResult(biomarker="Hemoglobin", value=11.2, unit="g/dL", ref_low=12, ref_high=16, flagged=True, flag_reason="Below reference range (12)"),
    VerifiedResult(biomarker="WBC", value=6.5, unit="10³/µL", ref_low=4.5, ref_high=11, flagged=False, flag_reason=None),
    VerifiedResult(biomarker="Glucose", value=92, unit="mg/dL", ref_low=70, ref_high=100, flagged=False, flag_reason=None),
]

ALL_NORMAL_RESULTS = [
    VerifiedResult(biomarker="Hemoglobin", value=14.5, unit="g/dL", ref_low=12, ref_high=16, flagged=False, flag_reason=None),
    VerifiedResult(biomarker="Glucose", value=92, unit="mg/dL", ref_low=70, ref_high=100, flagged=False, flag_reason=None),
    VerifiedResult(biomarker="Creatinine", value=0.9, unit="mg/dL", ref_low=0.6, ref_high=1.2, flagged=False, flag_reason=None),
]

METABOLIC_RESULTS = [
    VerifiedResult(biomarker="Glucose", value=108, unit="mg/dL", ref_low=70, ref_high=100, flagged=True, flag_reason="Above reference range (100)"),
    VerifiedResult(biomarker="HDL", value=34, unit="mg/dL", ref_low=40, ref_high=60, flagged=True, flag_reason="Below reference range (40)"),
    VerifiedResult(biomarker="Triglycerides", value=195, unit="mg/dL", ref_low=0, ref_high=150, flagged=True, flag_reason="Above reference range (150)"),
    VerifiedResult(biomarker="ALT", value=48, unit="U/L", ref_low=7, ref_high=40, flagged=True, flag_reason="Above reference range (40)"),
    VerifiedResult(biomarker="Uric Acid", value=7.8, unit="mg/dL", ref_low=3.5, ref_high=7.2, flagged=True, flag_reason="Above reference range (7.2)"),
]


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: Demo outputs are valid AnalysisOutput objects
# ═══════════════════════════════════════════════════════════════════════════

def test_demo_outputs_valid():
    """All 4 demo scenarios return valid AnalysisOutput."""
    for name, output in DEMO_SCENARIOS.items():
        assert isinstance(output, AnalysisOutput), f"{name}: not AnalysisOutput"
        assert output.summary, f"{name}: empty summary"
        assert output.disclaimer, f"{name}: missing disclaimer"
        assert len(output.patterns) >= 1, f"{name}: no patterns"

        for pattern in output.patterns:
            assert pattern.name, f"{name}: pattern has no name"
            assert pattern.severity in (Severity.WARNING, Severity.CAUTION, Severity.ADVISORY)
            assert pattern.confidence in (Confidence.HIGH, Confidence.MODERATE, Confidence.LOW)
            assert pattern.explanation, f"{name}: pattern has no explanation"
            assert len(pattern.supporting_markers) >= 1, f"{name}: no supporting markers"
            assert len(pattern.doctor_questions) >= 2, f"{name}: fewer than 2 doctor questions"
            assert len(pattern.citations) >= 1, f"{name}: no citations"

    print("✓ test_demo_outputs_valid PASSED")


def test_get_demo_output():
    """get_demo_output returns correct scenario or None."""
    assert get_demo_output("iron_deficiency") is not None
    assert get_demo_output("metabolic_syndrome") is not None
    assert get_demo_output("biotin_interference") is not None
    assert get_demo_output("hemolysis_artifact") is not None
    assert get_demo_output("nonexistent") is None

    print("✓ test_get_demo_output PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Context formatter produces sensible output
# ═══════════════════════════════════════════════════════════════════════════

def test_format_biomarker_table():
    """Only abnormal biomarkers appear in the formatted table."""
    result = format_biomarker_table(IRON_DEFICIENCY_RESULTS)
    assert "Ferritin" in result
    assert "MCV" in result
    assert "Hemoglobin" in result
    # Normal biomarkers should NOT appear
    assert "WBC" not in result
    assert "Glucose" not in result

    print("✓ test_format_biomarker_table PASSED")


def test_format_biomarker_table_all_normal():
    """All normal → returns 'all within range' message."""
    result = format_biomarker_table(ALL_NORMAL_RESULTS)
    assert "normal" in result.lower()

    print("✓ test_format_biomarker_table_all_normal PASSED")


def test_format_wearable_summary():
    """Wearable data formats correctly."""
    # With data
    result = format_wearable_summary({"resting_hr_avg": 76, "resting_hr_trend": "rising"})
    assert "76" in result
    assert "rising" in result

    # No data
    result = format_wearable_summary(None)
    assert "No wearable" in result

    # Empty dict
    result = format_wearable_summary({})
    assert "No wearable" in result

    print("✓ test_format_wearable_summary PASSED")


def test_format_medications():
    """Medications format as comma-separated list."""
    assert "Metformin" in format_medications(["Metformin", "Biotin"])
    assert "None" in format_medications(None)
    assert "None" in format_medications([])

    print("✓ test_format_medications PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Prompt assembly contains all parts
# ═══════════════════════════════════════════════════════════════════════════

def test_prompt_assembly():
    """Built prompt contains biomarkers, medications, and citations."""
    verification = VerificationOutput(
        verified_results=IRON_DEFICIENCY_RESULTS,
        drug_interferences=[],
        corrected_values=[],
        quality_flags=[],
    )

    prompt = _build_prompt(
        verified_results=IRON_DEFICIENCY_RESULTS,
        citations_formatted="[CITATION wallach_001] Iron deficiency is characterized by...",
        verification=verification,
        medications=["Metformin"],
        wearable_data={"resting_hr_avg": 76, "resting_hr_trend": "rising"},
    )

    assert "Ferritin" in prompt
    assert "Metformin" in prompt
    assert "76" in prompt
    assert "wallach_001" in prompt
    assert "CITATION" in prompt

    print("✓ test_prompt_assembly PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: JSON parsing handles various inputs
# ═══════════════════════════════════════════════════════════════════════════

def test_parse_valid_json():
    """Valid JSON produces AnalysisOutput."""
    valid_json = '''{
        "summary": "Test summary",
        "patterns": [
            {
                "name": "Test Pattern",
                "severity": "CAUTION",
                "confidence": "HIGH",
                "explanation": "Test explanation",
                "symptomatic_note": null,
                "supporting_markers": ["Ferritin: 12 ng/mL (Low)"],
                "citations": ["Wallach Ch.3"],
                "doctor_questions": ["Question 1?", "Question 2?"]
            }
        ],
        "verification_alerts": [],
        "disclaimer": "Not a diagnosis."
    }'''

    result = _parse_llm_output(valid_json)
    assert result is not None
    assert isinstance(result, AnalysisOutput)
    assert result.summary == "Test summary"
    assert len(result.patterns) == 1
    assert result.patterns[0].name == "Test Pattern"
    assert result.patterns[0].severity == Severity.CAUTION

    print("✓ test_parse_valid_json PASSED")


def test_parse_json_with_surrounding_text():
    """JSON extraction works even with text around it."""
    messy = '''Here is the analysis:
    {"summary": "Found pattern", "patterns": [], "verification_alerts": [], "disclaimer": "Not a diagnosis."}
    End of response.'''

    result = _parse_llm_output(messy)
    assert result is not None
    assert result.summary == "Found pattern"

    print("✓ test_parse_json_with_surrounding_text PASSED")


def test_parse_invalid_json():
    """Broken JSON returns None (no crash)."""
    assert _parse_llm_output("not json at all") is None
    assert _parse_llm_output("{broken: json}") is None
    assert _parse_llm_output("") is None

    print("✓ test_parse_invalid_json PASSED")


def test_parse_severity_normalization():
    """Severity values are normalized (case-insensitive, fallback to ADVISORY)."""
    json_str = '''{
        "summary": "Test",
        "patterns": [
            {
                "name": "P1", "severity": "warning", "confidence": "low",
                "explanation": "E", "supporting_markers": ["X"],
                "citations": ["C"], "doctor_questions": ["Q?"]
            },
            {
                "name": "P2", "severity": "INVALID", "confidence": "INVALID",
                "explanation": "E", "supporting_markers": ["X"],
                "citations": ["C"], "doctor_questions": ["Q?"]
            }
        ],
        "verification_alerts": [],
        "disclaimer": "D"
    }'''

    result = _parse_llm_output(json_str)
    assert result is not None
    assert result.patterns[0].severity == Severity.WARNING
    assert result.patterns[1].severity == Severity.ADVISORY  # fallback
    assert result.patterns[1].confidence == Confidence.MODERATE  # fallback

    print("✓ test_parse_severity_normalization PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Fast path — all normal
# ═══════════════════════════════════════════════════════════════════════════

def test_all_normal_fast_path():
    """All normal biomarkers → 'all normal' output, no patterns."""
    result = _all_normal_output(None)
    assert "normal" in result.summary.lower()
    assert len(result.patterns) == 0
    assert result.disclaimer

    print("✓ test_all_normal_fast_path PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Fallback chain — LLM unavailable
# ═══════════════════════════════════════════════════════════════════════════

def test_synthesize_fallback_to_demo():
    """When LLM is unavailable, synthesize falls back to demo output."""
    # This will fail to call LLM (not running) and should fall back
    result = synthesize(
        verified_results=IRON_DEFICIENCY_RESULTS,
        citations_formatted="[CITATION test] Some clinical text",
        verification=None,
        medications=None,
        wearable_data=None,
        use_demo_fallback=True,
    )

    # Should get a valid output (either from demo match or raw fallback)
    assert isinstance(result, AnalysisOutput)
    assert result.summary
    assert result.disclaimer

    print("✓ test_synthesize_fallback_to_demo PASSED")


def test_synthesize_all_normal():
    """All normal → fast path, no LLM call needed."""
    result = synthesize(
        verified_results=ALL_NORMAL_RESULTS,
        citations_formatted="",
        verification=None,
        medications=None,
        wearable_data=None,
    )

    assert isinstance(result, AnalysisOutput)
    assert "normal" in result.summary.lower()
    assert len(result.patterns) == 0

    print("✓ test_synthesize_all_normal PASSED")


def test_raw_fallback_output():
    """Raw fallback produces valid output with abnormal markers listed."""
    result = _raw_fallback_output(IRON_DEFICIENCY_RESULTS, None)

    assert isinstance(result, AnalysisOutput)
    assert len(result.patterns) == 1
    assert "Ferritin" in str(result.patterns[0].supporting_markers)
    assert result.patterns[0].severity == Severity.ADVISORY
    assert "unavailable" in result.summary.lower()

    print("✓ test_raw_fallback_output PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Demo scenario matching
# ═══════════════════════════════════════════════════════════════════════════

def test_match_demo_scenario():
    """Verified results are matched to the correct demo scenario."""
    # Iron deficiency
    result = match_demo_scenario(IRON_DEFICIENCY_RESULTS)
    assert result is not None
    assert "Iron" in result.patterns[0].name

    # Metabolic
    result = match_demo_scenario(METABOLIC_RESULTS)
    assert result is not None
    assert "Metabolic" in result.patterns[0].name

    # All normal → no match
    result = match_demo_scenario(ALL_NORMAL_RESULTS)
    assert result is None

    print("✓ test_match_demo_scenario PASSED")


# ═══════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        test_demo_outputs_valid,
        test_get_demo_output,
        test_format_biomarker_table,
        test_format_biomarker_table_all_normal,
        test_format_wearable_summary,
        test_format_medications,
        test_prompt_assembly,
        test_parse_valid_json,
        test_parse_json_with_surrounding_text,
        test_parse_invalid_json,
        test_parse_severity_normalization,
        test_all_normal_fast_path,
        test_synthesize_fallback_to_demo,
        test_synthesize_all_normal,
        test_raw_fallback_output,
        test_match_demo_scenario,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("All tests passed! ✓")
    else:
        print(f"FAILURES: {failed}")
        sys.exit(1)
