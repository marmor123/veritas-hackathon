"""
Test suite for the Verification Layer (Module 3).

Covers all 4 demo scenarios from the architecture:
  A. Iron deficiency — should produce no flags (clean abnormal pattern)
  B. Metabolic syndrome — should compute corrected LDL, no false flags
  C. Biotin interference — should flag TSH as drug-affected before clinical interpretation
  D. Hemolysis artifact — should flag high K+ with normal kidneys as likely hemolysis

Run: python -m backend.verification.test_verification
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.api.models.schemas import BiomarkerResult
from backend.verification.verifier import verify_results


def test_iron_deficiency():
    """Scenario A: Iron deficiency — clean clinical pattern, no false flags expected."""
    print("\n" + "=" * 70)
    print("SCENARIO A: Iron Deficiency (no false flags expected)")
    print("=" * 70)

    biomarkers = [
        BiomarkerResult(name="Ferritin", value=12, unit="ng/mL",
                        ref_low=15, ref_high=150, flag="L"),
        BiomarkerResult(name="Iron", value=35, unit="µg/dL",
                        ref_low=60, ref_high=170, flag="L"),
        BiomarkerResult(name="MCV", value=78, unit="fL",
                        ref_low=80, ref_high=100, flag="L"),
        BiomarkerResult(name="Hemoglobin", value=11.2, unit="g/dL",
                        ref_low=12, ref_high=16, flag="L"),
    ]

    result = verify_results(biomarkers, medications=["Iron Supplement"])

    # Verified results
    abnormal = [r for r in result.verified_results if r.flagged]
    print(f"  Abnormal biomarkers: {len(abnormal)}/4 expected: {[r.biomarker for r in abnormal]}")

    # Drug interference: iron supplement should flag iron studies
    print(f"  Drug interferences: {len(result.drug_interferences)}")
    for di in result.drug_interferences:
        print(f"    - {di.drug} affects {di.biomarker}: {di.effect}")

    # Quality flags: should be 0 (no hemolysis, no implausibility)
    print(f"  Quality flags: {len(result.quality_flags)}")
    for f in result.quality_flags:
        print(f"    - [{f.severity}] {f.type}: {f.detail[:80]}")

    # Validation
    print("\n  [Validation]")
    if len(abnormal) == 4:
        print("  ✓ All 4 abnormal biomarkers flagged")
    else:
        print(f"  ✗ Expected 4 abnormal, got {len(abnormal)}")

    if len(result.drug_interferences) >= 1:
        print(f"  ✓ Iron supplement interference detected ({len(result.drug_interferences)} flags)")
    else:
        print("  ✗ No iron supplement interference detected")


def test_metabolic_syndrome():
    """Scenario B: Metabolic syndrome — should compute Friedewald LDL and corrected Na."""
    print("\n" + "=" * 70)
    print("SCENARIO B: Metabolic Syndrome (corrected values expected)")
    print("=" * 70)

    biomarkers = [
        BiomarkerResult(name="Glucose", value=240, unit="mg/dL",
                        ref_low=70, ref_high=100, flag="H"),
        BiomarkerResult(name="HDL", value=34, unit="mg/dL",
                        ref_low=40, ref_high=100, flag="L"),
        BiomarkerResult(name="Cholesterol", value=240, unit="mg/dL",
                        ref_low=0, ref_high=200, flag="H"),
        BiomarkerResult(name="Triglycerides", value=195, unit="mg/dL",
                        ref_low=0, ref_high=150, flag="H"),
        BiomarkerResult(name="ALT", value=48, unit="U/L",
                        ref_low=0, ref_high=35, flag="H"),
        BiomarkerResult(name="Sodium", value=138, unit="mEq/L",
                        ref_low=135, ref_high=145),
    ]

    result = verify_results(biomarkers)

    print(f"  Corrected values: {len(result.corrected_values)}")
    for cv in result.corrected_values:
        print(f"    - {cv['name']}: {cv['corrected_value']} {cv['unit']} ({cv['formula']})")
        print(f"      {cv.get('interpretation', '')[:80]}")

    print("\n  [Validation]")
    has_ldl = any(cv["name"].startswith("LDL") for cv in result.corrected_values)
    has_corrected_na = any(cv["name"] == "Corrected Sodium" for cv in result.corrected_values)
    if has_ldl:
        print("  ✓ Friedewald LDL computed")
    else:
        print("  ✗ Friedewald LDL not computed")
    if has_corrected_na:
        print("  ✓ Corrected Sodium computed (glucose > 200)")
    else:
        print("  ✗ Corrected Sodium not computed")


def test_biotin_interference():
    """Scenario C: Biotin causes false thyroid results — interference should be flagged."""
    print("\n" + "=" * 70)
    print("SCENARIO C: Biotin Interference (drug flag expected BEFORE interpretation)")
    print("=" * 70)

    biomarkers = [
        BiomarkerResult(name="TSH", value=0.1, unit="mIU/L",
                        ref_low=0.4, ref_high=4.0, flag="L"),
        BiomarkerResult(name="Free T4", value=2.1, unit="ng/dL",
                        ref_low=0.8, ref_high=1.8, flag="H"),
    ]

    result = verify_results(biomarkers, supplements=["Biotin 10000mcg"])

    print(f"  Drug interferences: {len(result.drug_interferences)}")
    for di in result.drug_interferences:
        print(f"    - {di.drug} affects {di.biomarker}: {di.effect}")
        print(f"      → {di.recommendation}")

    print("\n  [Validation]")
    biotin_flags = [di for di in result.drug_interferences if "biotin" in di.drug.lower()]
    if len(biotin_flags) >= 1:
        print(f"  ✓ Biotin interference flagged ({len(biotin_flags)} biomarkers affected)")
    else:
        print("  ✗ Biotin interference NOT flagged — false positive thyroid disease risk")


def test_hemolysis_artifact():
    """Scenario D: Very high K+ with normal kidneys — should flag hemolysis."""
    print("\n" + "=" * 70)
    print("SCENARIO D: Hemolysis Artifact (high K+ + normal kidneys)")
    print("=" * 70)

    biomarkers = [
        BiomarkerResult(name="Potassium", value=6.8, unit="mmol/L",
                        ref_low=3.5, ref_high=5.0, flag="H"),
        BiomarkerResult(name="Creatinine", value=0.9, unit="mg/dL",
                        ref_low=0.6, ref_high=1.3),
        BiomarkerResult(name="eGFR", value=95, unit="mL/min",
                        ref_low=60),
    ]

    result = verify_results(biomarkers)

    print(f"  Quality flags: {len(result.quality_flags)}")
    for f in result.quality_flags:
        print(f"    - [{f.severity}] {f.type}: {f.detail[:120]}")

    print("\n  [Validation]")
    hemolysis_flags = [f for f in result.quality_flags if f.type == "hemolysis"]
    if hemolysis_flags:
        print(f"  ✓ Hemolysis flag raised ({len(hemolysis_flags)})")
    else:
        print("  ✗ No hemolysis flag — would falsely interpret as hyperkalemia")


def test_all_normal():
    """Scenario E: All normal — no flags, no corrections expected."""
    print("\n" + "=" * 70)
    print("SCENARIO E: All Normal")
    print("=" * 70)

    biomarkers = [
        BiomarkerResult(name="Hemoglobin", value=14.5, unit="g/dL",
                        ref_low=12, ref_high=16),
        BiomarkerResult(name="Glucose", value=92, unit="mg/dL",
                        ref_low=70, ref_high=100),
        BiomarkerResult(name="TSH", value=2.1, unit="mIU/L",
                        ref_low=0.4, ref_high=4.0),
        BiomarkerResult(name="Creatinine", value=0.9, unit="mg/dL",
                        ref_low=0.6, ref_high=1.3),
    ]

    result = verify_results(biomarkers)

    abnormal = [r for r in result.verified_results if r.flagged]
    print(f"  Abnormal biomarkers: {len(abnormal)} (expected 0)")
    print(f"  Quality flags: {len(result.quality_flags)} (expected 0)")
    print(f"  Drug interferences: {len(result.drug_interferences)} (expected 0)")

    print("\n  [Validation]")
    if len(abnormal) == 0:
        print("  ✓ All results recognized as normal")
    else:
        print(f"  ✗ {len(abnormal)} results incorrectly flagged abnormal")


def main():
    print("VERITAS Verification Layer — Test Suite")
    print("Module 3: catches errors and drug interference BEFORE clinical interpretation")

    test_iron_deficiency()
    test_metabolic_syndrome()
    test_biotin_interference()
    test_hemolysis_artifact()
    test_all_normal()

    print("\n" + "=" * 70)
    print("TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
