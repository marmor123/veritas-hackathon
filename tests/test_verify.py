"""
Tests for POST /api/verify — Verification Layer (Module 3).

Covers: drug interference, hemolysis, plausibility, corrected values,
edge cases, and error handling.
"""

import pytest
from tests.conftest import to_dict


class TestVerifyEndpoint:
    """POST /api/verify — basic endpoint behavior."""

    def test_verify_returns_200(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        assert response.status_code == 200
        data = response.json()
        assert "verified_results" in data
        assert "drug_interferences" in data
        assert "corrected_values" in data
        assert "quality_flags" in data

    def test_empty_biomarkers(self, client):
        response = client.post("/api/verify", json={"biomarkers": []})
        assert response.status_code == 200
        data = response.json()
        assert data["verified_results"] == []
        assert data["quality_flags"] == []

    def test_invalid_json(self, client):
        response = client.post("/api/verify", json={"wrong_key": []})
        assert response.status_code == 422  # Pydantic validation error


class TestVerifiedResults:
    """VerifiedResult flagging logic."""

    def test_abnormal_flagged(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        abnormal = [r for r in data["verified_results"] if r["flagged"]]
        # Ferritin, Iron, MCV, Hemoglobin should all be flagged
        assert len(abnormal) == 4
        names = {r["biomarker"] for r in abnormal}
        assert names == {"Ferritin", "Iron", "MCV", "Hemoglobin"}

    def test_all_normal_not_flagged(self, client, all_normal_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(all_normal_biomarkers),
        })
        data = response.json()
        abnormal = [r for r in data["verified_results"] if r["flagged"]]
        assert len(abnormal) == 0

    def test_flag_reasons_are_set(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        ferritin = [r for r in data["verified_results"] if r["biomarker"] == "Ferritin"][0]
        assert ferritin["flagged"] is True
        assert ferritin["flag_reason"] is not None
        assert "Below" in ferritin["flag_reason"] or "below" in ferritin["flag_reason"]


class TestDrugInterference:
    """Drug-lab interference detection."""

    def test_biotin_interferes_with_tsh(self, client, biotin_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(biotin_biomarkers),
            "supplements": ["Biotin 10000mcg"],
        })
        data = response.json()
        interferences = data["drug_interferences"]
        assert len(interferences) >= 1
        biotin_flags = [i for i in interferences if "biotin" in i["drug"].lower()]
        assert len(biotin_flags) >= 1
        affected = [i["biomarker"] for i in biotin_flags]
        assert "TSH" in affected

    def test_iron_supplement_flags_iron_studies(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
            "supplements": ["Iron Supplement"],
        })
        data = response.json()
        iron_flags = [i for i in data["drug_interferences"]
                      if "iron" in i["drug"].lower()]
        assert len(iron_flags) >= 1

    def test_no_drug_interference_without_medications(self, client, biotin_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(biotin_biomarkers),
        })
        data = response.json()
        assert data["drug_interferences"] == []

    def test_drug_interference_skips_normal_biomarkers(self, client):
        """Drug effects on normal results should not be flagged."""
        # High TSH but NOT on biotin — no interference should fire
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "TSH", "value": 5.5, "unit": "mIU/L",
                 "ref_low": 0.4, "ref_high": 4.0, "flag": "H"},
            ],
            "supplements": [],  # No biotin — interference checks drugs, not values
        })
        data = response.json()
        assert data["drug_interferences"] == []

    def test_creatine_elevates_creatinine(self, client):
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "Creatinine", "value": 1.5, "unit": "mg/dL",
                 "ref_low": 0.6, "ref_high": 1.2, "flag": "H"},
            ],
            "supplements": ["Creatine Monohydrate"],
        })
        data = response.json()
        creatine_flags = [i for i in data["drug_interferences"]
                          if "creatine" in i["drug"].lower()]
        assert len(creatine_flags) >= 1


class TestHemolysis:
    """Hemolysis artifact detection."""

    def test_high_k_with_normal_kidneys(self, client, hemolysis_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(hemolysis_biomarkers),
        })
        data = response.json()
        hemolysis_flags = [f for f in data["quality_flags"]
                           if f["type"] == "hemolysis"]
        assert len(hemolysis_flags) >= 1
        assert "Potassium" in hemolysis_flags[0]["affected_biomarkers"]

    def test_no_hemolysis_with_normal_potassium(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        hemolysis_flags = [f for f in data["quality_flags"]
                           if f["type"] == "hemolysis"]
        assert len(hemolysis_flags) == 0

    def test_extreme_potassium_severity(self, client):
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "Potassium", "value": 8.2, "unit": "mmol/L",
                 "ref_low": 3.5, "ref_high": 5.0, "flag": "H"},
                {"name": "Creatinine", "value": 0.8, "unit": "mg/dL",
                 "ref_low": 0.6, "ref_high": 1.2},
            ],
        })
        data = response.json()
        high_severity = [f for f in data["quality_flags"]
                         if f["severity"] == "high"]
        assert len(high_severity) >= 1  # K+ > 7.0 should be "high"


class TestPlausibility:
    """Physiological plausibility checks."""

    def test_tsh_ft4_inconsistent_both_high(self, client):
        """Both TSH and FT4 elevated — unusual, flag it."""
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "TSH", "value": 6.0, "unit": "mIU/L",
                 "ref_low": 0.4, "ref_high": 4.0, "flag": "H"},
                {"name": "Free T4", "value": 2.2, "unit": "ng/dL",
                 "ref_low": 0.8, "ref_high": 1.8, "flag": "H"},
            ],
        })
        data = response.json()
        plausibility_flags = [f for f in data["quality_flags"]
                              if f["type"] == "plausibility"]
        assert len(plausibility_flags) >= 1
        flag = plausibility_flags[0]
        assert "TSH" in flag["affected_biomarkers"]

    def test_tsh_ft4_consistent_no_flag(self, client):
        """High TSH + low FT4 = primary hypothyroidism — consistent, no flag."""
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "TSH", "value": 12.5, "unit": "mIU/L",
                 "ref_low": 0.4, "ref_high": 4.0, "flag": "H"},
                {"name": "Free T4", "value": 0.5, "unit": "ng/dL",
                 "ref_low": 0.8, "ref_high": 1.8, "flag": "L"},
            ],
        })
        data = response.json()
        plausibility_flags = [f for f in data["quality_flags"]
                              if f["type"] == "plausibility"]
        # High TSH + low FT4 is consistent — should not produce a
        # plausibility flag about inconsistency
        inconsistency = [f for f in plausibility_flags
                         if "TSH" in f["affected_biomarkers"]
                         and "Free T4" in f["affected_biomarkers"]]
        assert len(inconsistency) == 0


class TestCorrectedValues:
    """Corrected/derived values computation."""

    def test_lipid_panel_produces_friedewald_ldl(self, client):
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "Cholesterol", "value": 240, "unit": "mg/dL",
                 "ref_low": 0, "ref_high": 200, "flag": "H"},
                {"name": "HDL", "value": 45, "unit": "mg/dL",
                 "ref_low": 40, "ref_high": 60},
                {"name": "Triglycerides", "value": 150, "unit": "mg/dL",
                 "ref_low": 0, "ref_high": 150},
            ],
        })
        data = response.json()
        ldl = [cv for cv in data["corrected_values"]
               if "LDL" in cv.get("name", "")]
        assert len(ldl) >= 1
        # Friedewald: 240 - 45 - 150/5 = 240 - 45 - 30 = 165
        assert ldl[0]["corrected_value"] == pytest.approx(165.0, rel=0.01)

    def test_no_ldl_when_direct_ldl_present(self, client):
        """Don't compute Friedewald if direct LDL is already measured."""
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "Cholesterol", "value": 240, "unit": "mg/dL",
                 "ref_low": 0, "ref_high": 200},
                {"name": "HDL", "value": 45, "unit": "mg/dL",
                 "ref_low": 40, "ref_high": 60},
                {"name": "Triglycerides", "value": 150, "unit": "mg/dL",
                 "ref_low": 0, "ref_high": 150},
                {"name": "LDL", "value": 130, "unit": "mg/dL",
                 "ref_low": 0, "ref_high": 100},
            ],
        })
        data = response.json()
        ldl = [cv for cv in data["corrected_values"]
               if "LDL" in cv.get("name", "")]
        assert len(ldl) == 0  # Direct LDL present — skip Friedewald

    def test_corrected_sodium_with_hyperglycemia(self, client):
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "Sodium", "value": 132, "unit": "mEq/L",
                 "ref_low": 135, "ref_high": 145, "flag": "L"},
                {"name": "Glucose", "value": 400, "unit": "mg/dL",
                 "ref_low": 70, "ref_high": 100, "flag": "H"},
            ],
        })
        data = response.json()
        corrected_na = [cv for cv in data["corrected_values"]
                        if "Sodium" in cv.get("name", "")]
        assert len(corrected_na) >= 1
        expected = 132 + 0.016 * (400 - 100)  # = 132 + 4.8 = 136.8
        assert corrected_na[0]["corrected_value"] == pytest.approx(expected, rel=0.1)

    def test_anion_gap_computed(self, client):
        response = client.post("/api/verify", json={
            "biomarkers": [
                {"name": "Sodium", "value": 140, "unit": "mEq/L",
                 "ref_low": 135, "ref_high": 145},
                {"name": "Chloride", "value": 100, "unit": "mEq/L",
                 "ref_low": 98, "ref_high": 106},
                {"name": "CO2", "value": 24, "unit": "mEq/L",
                 "ref_low": 22, "ref_high": 30},
            ],
        })
        data = response.json()
        anion_gap = [cv for cv in data["corrected_values"]
                     if "Anion" in cv.get("name", "")]
        assert len(anion_gap) >= 1
        assert anion_gap[0]["corrected_value"] == pytest.approx(16.0, rel=0.1)
