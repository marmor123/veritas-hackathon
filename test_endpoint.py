"""
Integration test: Hit the /api/analyze endpoint via FastAPI TestClient.

Tests the actual endpoint behavior including:
  1. Hemolysis early halt (K+ = 7.5) — should return immediately with no patterns
  2. K+ = 6.8 with normal eGFR — medium severity, pipeline continues
  3. Iron deficiency — full pipeline with mocked RAG/LLM

We mock heavy dependencies (ollama, sentence_transformers, lancedb) at import
level to avoid needing them installed.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock heavy dependencies before importing anything from backend
from unittest.mock import MagicMock, patch
sys.modules['ollama'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['lancedb'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['tqdm'] = MagicMock()
sys.modules['tqdm.auto'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()
sys.modules['fitz'] = MagicMock()

import asyncio
from httpx import AsyncClient, ASGITransport

from backend.api.models.schemas import (
    AnalysisOutput, PatternResult, Severity, Confidence, ClinicalGraph,
)
from backend.main import app


async def test_hemolysis_early_halt_endpoint():
    """POST /api/analyze with K+=7.5 should halt early — no RAG, no LLM called."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/analyze", json={
            "biomarkers": [
                {"name": "Potassium", "value": 7.5, "unit": "mmol/L", "ref_low": 3.5, "ref_high": 5.0, "flag": "H"},
                {"name": "eGFR", "value": 90.0, "unit": "mL/min/1.73m2", "ref_low": 60.0, "flag": None},
                {"name": "Creatinine", "value": 0.9, "unit": "mg/dL", "ref_low": 0.6, "ref_high": 1.3, "flag": None},
            ],
            "medications": None,
        })

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    # Verify early halt behavior
    assert data["patterns"] == [], f"Expected empty patterns, got: {data['patterns']}"
    assert "unreliable" in data["summary"], f"Summary should mention unreliable: {data['summary']}"
    assert len(data["verification_alerts"]) > 0, "Should have at least one alert"
    assert "repeating the blood test" in data["verification_alerts"][0]["recommendation"]

    print("[PASS] Endpoint Test 1: K+=7.5 triggers early halt correctly")
    print(f"       Status: {response.status_code}")
    print(f"       Summary: {data['summary'][:60]}...")
    print(f"       Patterns: {len(data['patterns'])} (empty)")
    print(f"       Alerts: {len(data['verification_alerts'])}")
    return True


async def test_iron_deficiency_endpoint():
    """
    POST /api/analyze with iron deficiency — should NOT halt early.
    We mock RAG and LLM to avoid needing Ollama running.
    """
    mock_rag_result = {
        "rag_output": MagicMock(),
        "citations": [],
        "citations_formatted": "Wallach Ch.11: Iron deficiency...",
        "clinical_graph": ClinicalGraph(nodes=[], edges=[]),
        "timings": {},
        "rewritten_query": "iron deficiency anemia",
    }

    mock_analysis = AnalysisOutput(
        summary="Iron deficiency pattern detected with microcytic anemia.",
        patterns=[
            PatternResult(
                name="Iron Deficiency Anemia",
                severity=Severity.CAUTION,
                confidence=Confidence.HIGH,
                explanation="Low ferritin, iron, hemoglobin, and MCV indicate iron deficiency anemia.",
                supporting_markers=["Ferritin", "Iron", "Hemoglobin", "MCV"],
                citations=["Wallach Ch.11"],
                doctor_questions=["Should I start iron supplementation?"],
            )
        ],
        verification_alerts=[],
        disclaimer="This is not a medical diagnosis.",
    )

    with patch("backend.api.routes.analysis._get_pipeline") as mock_pipeline, \
         patch("backend.api.routes.analysis.synthesize") as mock_synth:

        mock_pipeline.return_value.run.return_value = mock_rag_result
        mock_synth.return_value = mock_analysis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/analyze", json={
                "biomarkers": [
                    {"name": "Ferritin", "value": 8.0, "unit": "ng/mL", "ref_low": 15.0, "ref_high": 150.0, "flag": "L"},
                    {"name": "Iron", "value": 30.0, "unit": "ug/dL", "ref_low": 60.0, "ref_high": 170.0, "flag": "L"},
                    {"name": "Hemoglobin", "value": 10.5, "unit": "g/dL", "ref_low": 12.0, "ref_high": 16.0, "flag": "L"},
                    {"name": "MCV", "value": 72.0, "unit": "fL", "ref_low": 80.0, "ref_high": 100.0, "flag": "L"},
                ],
                "medications": ["omeprazole"],
            })

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    # Verify full pipeline ran (patterns present)
    assert len(data["patterns"]) > 0, f"Expected patterns, got none"
    assert "Iron" in data["patterns"][0]["name"], f"Expected iron pattern, got: {data['patterns'][0]['name']}"

    print("[PASS] Endpoint Test 2: Iron deficiency runs full pipeline")
    print(f"       Status: {response.status_code}")
    print(f"       Summary: {data['summary'][:60]}...")
    print(f"       Patterns: {len(data['patterns'])}")
    print(f"       Alerts: {len(data['verification_alerts'])}")
    return True


async def test_medium_severity_passthrough_endpoint():
    """
    POST /api/analyze with K+=6.8 (medium severity) — should NOT halt.
    Pipeline continues; medium flag appears in verification_alerts.
    """
    mock_rag_result = {
        "rag_output": MagicMock(),
        "citations": [],
        "citations_formatted": "Clinical reference...",
        "clinical_graph": ClinicalGraph(nodes=[], edges=[]),
        "timings": {},
        "rewritten_query": "hyperkalemia",
    }

    mock_analysis = AnalysisOutput(
        summary="Elevated potassium detected.",
        patterns=[
            PatternResult(
                name="Elevated Potassium",
                severity=Severity.CAUTION,
                confidence=Confidence.MODERATE,
                explanation="Potassium is elevated.",
                supporting_markers=["Potassium"],
                citations=["Wallach Ch.5"],
                doctor_questions=["Is this a true elevation?"],
            )
        ],
        verification_alerts=[],
        disclaimer="This is not a medical diagnosis.",
    )

    with patch("backend.api.routes.analysis._get_pipeline") as mock_pipeline, \
         patch("backend.api.routes.analysis.synthesize") as mock_synth:

        mock_pipeline.return_value.run.return_value = mock_rag_result
        mock_synth.return_value = mock_analysis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/analyze", json={
                "biomarkers": [
                    {"name": "Potassium", "value": 6.8, "unit": "mmol/L", "ref_low": 3.5, "ref_high": 5.0, "flag": "H"},
                    {"name": "eGFR", "value": 90.0, "unit": "mL/min/1.73m2", "ref_low": 60.0, "flag": None},
                    {"name": "Creatinine", "value": 0.9, "unit": "mg/dL", "ref_low": 0.6, "ref_high": 1.3, "flag": None},
                ],
                "medications": None,
            })

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    # Pipeline should NOT have halted — patterns should exist
    assert len(data["patterns"]) > 0, f"Expected patterns (no early halt), got none"

    # Medium-severity flag should appear in verification_alerts
    has_hemolysis_alert = any(
        "potassium" in alert.get("biomarker", "").lower() or
        "hemolysis" in alert.get("issue", "").lower()
        for alert in data["verification_alerts"]
    )
    assert has_hemolysis_alert, f"Expected hemolysis alert in verification_alerts: {data['verification_alerts']}"

    print("[PASS] Endpoint Test 3: K+=6.8 (medium) does NOT halt, flag passed through")
    print(f"       Status: {response.status_code}")
    print(f"       Patterns: {len(data['patterns'])} (pipeline ran)")
    print(f"       Alerts: {len(data['verification_alerts'])}")
    print(f"       Has hemolysis alert: {has_hemolysis_alert}")
    return True


async def main():
    print("=" * 70)
    print("VERITAS — Endpoint Integration Tests")
    print("=" * 70)
    print()

    results = []
    results.append(await test_hemolysis_early_halt_endpoint())
    print()
    results.append(await test_iron_deficiency_endpoint())
    print()
    results.append(await test_medium_severity_passthrough_endpoint())
    print()

    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} endpoint tests passed")
    if all(results):
        print("ALL ENDPOINT TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
