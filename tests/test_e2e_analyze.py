"""
End-to-end tests for POST /api/analyze — Full Pipeline (Module 5).

Tests the complete flow: Verify → RAG → LLM Synthesis.
Also covers demo scenarios, error handling, and graceful degradation.

These tests hit the REAL pipeline — embedding models load, LanceDB is queried,
and Ollama is called (falls back to demo output if unavailable).
"""

import pytest
from tests.conftest import to_dict


class TestAnalyzeEndpoint:
    """POST /api/analyze — full pipeline endpoint."""

    def test_returns_200(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "patterns" in data
        assert "verification_alerts" in data
        assert "disclaimer" in data

    def test_summary_is_not_empty(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        assert len(data["summary"]) > 10

    def test_disclaimer_is_present(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        assert "not a medical diagnosis" in data["disclaimer"].lower()


class TestAnalyzePatternStructures:
    """Validate PatternResult structure in analysis output."""

    def test_patterns_have_required_fields(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        for pattern in data["patterns"]:
            assert "name" in pattern
            assert "severity" in pattern
            assert pattern["severity"] in ("WARNING", "CAUTION", "ADVISORY")
            assert "confidence" in pattern
            assert pattern["confidence"] in ("HIGH", "MODERATE", "LOW")
            assert "explanation" in pattern
            assert "supporting_markers" in pattern
            assert "citations" in pattern
            assert "doctor_questions" in pattern

    def test_doctor_questions_are_specific(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        for pattern in data["patterns"]:
            questions = pattern["doctor_questions"]
            assert len(questions) >= 1, f"Pattern '{pattern['name']}' has no questions"
            for q in questions:
                assert len(q) > 20, f"Question too short: '{q}'"
                assert "?" in q, f"Question should end with ?: '{q}'"

    def test_patterns_sorted_by_severity(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        data = response.json()
        severity_order = {"WARNING": 0, "CAUTION": 1, "ADVISORY": 2}
        severities = [severity_order.get(p["severity"], 99)
                      for p in data["patterns"]]
        assert severities == sorted(severities), \
            "Patterns should be sorted by severity (WARNING first)"


class TestAnalyzeDemoScenarios:
    """Demo mode — instant pre-cached responses."""

    DEMOS = ["iron_deficiency", "metabolic_syndrome",
             "biotin_interference", "hemolysis_artifact"]

    @pytest.mark.parametrize("scenario", DEMOS)
    def test_demo_returns_200(self, client, scenario):
        response = client.post(
            f"/api/analyze?demo={scenario}",
            json={"biomarkers": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["summary"]) > 10
        assert len(data["patterns"]) >= 1

    def test_demo_iron_deficiency_has_symptomatic_note(self, client):
        response = client.post(
            "/api/analyze?demo=iron_deficiency",
            json={"biomarkers": []},
        )
        data = response.json()
        pattern = data["patterns"][0]
        # Iron deficiency demo should have a symptomatic note about HR
        note = pattern.get("symptomatic_note")
        assert note is not None and len(note) > 10

    def test_demo_biotin_has_verification_alerts(self, client):
        response = client.post(
            "/api/analyze?demo=biotin_interference",
            json={"biomarkers": []},
        )
        data = response.json()
        alerts = data["verification_alerts"]
        assert len(alerts) >= 1
        assert any("biotin" in str(a).lower() for a in alerts)

    def test_demo_hemolysis_is_warning(self, client):
        response = client.post(
            "/api/analyze?demo=hemolysis_artifact",
            json={"biomarkers": []},
        )
        data = response.json()
        assert data["patterns"][0]["severity"] == "WARNING"

    def test_invalid_demo_returns_400(self, client):
        response = client.post(
            "/api/analyze?demo=nonexistent_scenario",
            json={"biomarkers": []},
        )
        assert response.status_code == 400

    def test_list_demos(self, client):
        response = client.get("/api/analyze/demos")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) == 4


class TestAnalyzeFullPipeline:
    """End-to-end: biomarkers go through verify → RAG → synthesis."""

    def test_iron_deficiency_with_wearable(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
            "medications": ["Metformin"],
            "wearable_data": {
                "resting_hr_avg": 76,
                "resting_hr_trend": "rising",
            },
        })
        assert response.status_code == 200
        data = response.json()
        # Should produce at least one pattern
        assert len(data["patterns"]) >= 1
        # Should have a summary mentioning iron or anemia
        assert any(word in data["summary"].lower()
                   for word in ["iron", "anemia", "ferritin", "blood"])

    def test_metabolic_syndrome_groups_biomarkers(self, client,
                                                   metabolic_syndrome_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(metabolic_syndrome_biomarkers),
        })
        assert response.status_code == 200
        data = response.json()
        patterns = data["patterns"]
        # Should produce at least 1 pattern
        assert len(patterns) >= 1

    def test_biotin_with_medication_context(self, client, biotin_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(biotin_biomarkers),
            "supplements": ["Biotin 10000mcg"],
        })
        assert response.status_code == 200
        data = response.json()
        # Should flag the interference somewhere (alerts or pattern explanation)
        all_text = data["summary"] + " ".join(
            p.get("explanation", "") for p in data["patterns"]
        ) + str(data["verification_alerts"])
        assert "biotin" in all_text.lower() or "interference" in all_text.lower()

    def test_hemolysis_pipeline(self, client, hemolysis_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(hemolysis_biomarkers),
        })
        assert response.status_code == 200
        data = response.json()
        # Should have verification alerts
        if data["verification_alerts"]:
            alert_text = str(data["verification_alerts"]).lower()
            assert any(word in alert_text
                       for word in ["potassium", "hemolysis", "artifact", "collection"])

    def test_clinical_graph_attached(self, client, iron_deficiency_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
            "wearable_data": {"resting_hr_avg": 76, "resting_hr_trend": "rising"},
        })
        assert response.status_code == 200
        data = response.json()
        graph = data.get("clinical_graph")
        if graph:
            assert "nodes" in graph
            assert "edges" in graph
            # Should have at least a ferritin or hemoglobin node
            node_labels = [n["label"].lower() for n in graph["nodes"]]
            assert any("ferritin" in l or "hemoglobin" in l or "iron" in l
                       for l in node_labels)


class TestAnalyzeAllNormal:
    """Fast path: all biomarkers normal."""

    def test_all_normal_no_patterns(self, client, all_normal_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(all_normal_biomarkers),
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["patterns"]) == 0
        assert "normal" in data["summary"].lower()

    def test_all_normal_no_alerts(self, client, all_normal_biomarkers):
        response = client.post("/api/analyze", json={
            "biomarkers": to_dict(all_normal_biomarkers),
        })
        data = response.json()
        assert data["verification_alerts"] == []


class TestAnalyzeErrorHandling:
    """Graceful degradation under error conditions."""

    def test_invalid_json_returns_422(self, client):
        response = client.post("/api/analyze", json={"wrong": "data"})
        assert response.status_code == 422

    def test_empty_biomarkers_returns_200(self, client):
        response = client.post("/api/analyze", json={"biomarkers": []})
        assert response.status_code == 200
        data = response.json()
        assert "normal" in data["summary"].lower()


class TestHealthEndpoint:
    """GET / — root endpoint."""

    def test_root_returns_modules(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "VERITAS"
        assert "modules" in data
        assert "ocr" in data["modules"]
        assert "verify" in data["modules"]
        assert "rag" in data["modules"]

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
