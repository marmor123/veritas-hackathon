"""
Shared test fixtures for VERITAS backend tests.

Provides:
  - FastAPI TestClient (no need to start uvicorn)
  - Sample biomarker data for all 4 demo scenarios
  - Standard test inputs for OCR, verify, RAG, and analyze endpoints
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.models.schemas import BiomarkerResult


# ── FastAPI TestClient ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient — calls the real app, no network needed."""
    with TestClient(app) as c:
        yield c


# ── Sample biomarker data ──────────────────────────────────────────────────

@pytest.fixture
def iron_deficiency_biomarkers():
    """Low ferritin, iron, MCV, hemoglobin — classic iron deficiency pattern."""
    return [
        BiomarkerResult(name="Ferritin", value=12, unit="ng/mL",
                        ref_low=15, ref_high=150, flag="L"),
        BiomarkerResult(name="Iron", value=35, unit="ug/dL",
                        ref_low=60, ref_high=170, flag="L"),
        BiomarkerResult(name="MCV", value=78, unit="fL",
                        ref_low=80, ref_high=100, flag="L"),
        BiomarkerResult(name="Hemoglobin", value=11.2, unit="g/dL",
                        ref_low=12, ref_high=16, flag="L"),
        BiomarkerResult(name="Glucose", value=92, unit="mg/dL",
                        ref_low=70, ref_high=100),
        BiomarkerResult(name="Creatinine", value=0.9, unit="mg/dL",
                        ref_low=0.6, ref_high=1.2),
    ]


@pytest.fixture
def metabolic_syndrome_biomarkers():
    """High glucose, low HDL, high TG, high ALT, high uric acid."""
    return [
        BiomarkerResult(name="Glucose", value=108, unit="mg/dL",
                        ref_low=70, ref_high=100, flag="H"),
        BiomarkerResult(name="HDL", value=34, unit="mg/dL",
                        ref_low=40, ref_high=60, flag="L"),
        BiomarkerResult(name="Triglycerides", value=195, unit="mg/dL",
                        ref_low=0, ref_high=150, flag="H"),
        BiomarkerResult(name="ALT", value=48, unit="U/L",
                        ref_low=0, ref_high=35, flag="H"),
        BiomarkerResult(name="Uric Acid", value=7.8, unit="mg/dL",
                        ref_low=3.5, ref_high=7.2, flag="H"),
        BiomarkerResult(name="Hemoglobin", value=14.5, unit="g/dL",
                        ref_low=12, ref_high=16),
    ]


@pytest.fixture
def biotin_biomarkers():
    """Low TSH + normal FT4 + biotin supplement — drug interference pattern."""
    return [
        BiomarkerResult(name="TSH", value=0.15, unit="mIU/L",
                        ref_low=0.4, ref_high=4.0, flag="L"),
        BiomarkerResult(name="Free T4", value=1.3, unit="ng/dL",
                        ref_low=0.8, ref_high=1.8),
        BiomarkerResult(name="Hemoglobin", value=13.8, unit="g/dL",
                        ref_low=12, ref_high=16),
        BiomarkerResult(name="Glucose", value=88, unit="mg/dL",
                        ref_low=70, ref_high=100),
    ]


@pytest.fixture
def hemolysis_biomarkers():
    """High K+ + normal kidney + high LDH — hemolysis artifact pattern."""
    return [
        BiomarkerResult(name="Potassium", value=6.8, unit="mmol/L",
                        ref_low=3.5, ref_high=5.0, flag="H"),
        BiomarkerResult(name="LDH", value=380, unit="U/L",
                        ref_low=140, ref_high=280, flag="H"),
        BiomarkerResult(name="Creatinine", value=0.9, unit="mg/dL",
                        ref_low=0.6, ref_high=1.2),
        BiomarkerResult(name="eGFR", value=95, unit="mL/min",
                        ref_low=60),
        BiomarkerResult(name="Glucose", value=45, unit="mg/dL",
                        ref_low=70, ref_high=100, flag="L"),
    ]


@pytest.fixture
def all_normal_biomarkers():
    """All values within reference ranges."""
    return [
        BiomarkerResult(name="Hemoglobin", value=14.5, unit="g/dL",
                        ref_low=12, ref_high=16),
        BiomarkerResult(name="Glucose", value=92, unit="mg/dL",
                        ref_low=70, ref_high=100),
        BiomarkerResult(name="Creatinine", value=0.9, unit="mg/dL",
                        ref_low=0.6, ref_high=1.2),
        BiomarkerResult(name="TSH", value=2.1, unit="mIU/L",
                        ref_low=0.4, ref_high=4.0),
    ]


# ── Dict helpers (for JSON request bodies) ─────────────────────────────────

def to_dict(biomarkers: list[BiomarkerResult]) -> list[dict]:
    """Convert BiomarkerResult list to dicts for JSON requests."""
    return [
        {
            "name": b.name,
            "value": b.value,
            "unit": b.unit,
            "ref_low": b.ref_low,
            "ref_high": b.ref_high,
            "flag": b.flag,
        }
        for b in biomarkers
    ]
