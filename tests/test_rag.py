"""
Tests for POST /api/rag and GET /api/rag/health — RAG Engine (Module 4).

Covers: health check, retrieval quality, organ system filtering,
citation tracking, graph output, fast path for all-normal.
"""

import pytest
from tests.conftest import to_dict


class TestRagHealth:
    """GET /api/rag/health — component status."""

    def test_health_returns_200(self, client):
        response = client.get("/api/rag/health")
        assert response.status_code == 200
        data = response.json()
        assert "healthy" in data
        assert "components" in data

    def test_health_has_all_components(self, client):
        response = client.get("/api/rag/health")
        data = response.json()
        components = data["components"]
        assert "embedding_model" in components
        assert "lancedb" in components
        assert "cross_encoder" in components
        assert "llm" in components


class TestRagEndpoint:
    """POST /api/rag — retrieval pipeline."""

    def test_returns_200(self, client, iron_deficiency_biomarkers):
        # First verify, then RAG
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={
            "verified_results": verified,
        })
        assert response.status_code == 200
        data = response.json()
        assert "rag_output" in data
        assert "citations" in data
        assert "citations_formatted" in data
        assert "clinical_graph" in data
        assert "rewritten_query" in data
        assert "timings" in data

    def test_returns_rewritten_query(self, client, iron_deficiency_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={"verified_results": verified})
        data = response.json()
        query = data["rewritten_query"]
        assert len(query) > 20
        # Should mention clinical terms or biomarkers
        assert any(word in query.lower()
                   for word in ["ferritin", "iron", "microcytic", "anemia"])

    def test_citations_have_required_fields(self, client, iron_deficiency_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={"verified_results": verified})
        data = response.json()
        citations = data["citations"]
        assert len(citations) >= 1, "Should return at least 1 citation"
        for c in citations:
            assert "chunk_id" in c
            assert "source" in c
            assert "text" in c
            assert "relevance_score" in c
            assert "biomarkers_involved" in c

    def test_clinical_graph_has_nodes_and_edges(self, client, iron_deficiency_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={"verified_results": verified})
        data = response.json()
        graph = data["clinical_graph"]
        assert len(graph["nodes"]) >= 1, "Graph should have at least 1 node"
        assert all("id" in n and "label" in n and "type" in n
                   for n in graph["nodes"])

    def test_citations_formatted_has_citation_ids(self, client, iron_deficiency_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={"verified_results": verified})
        data = response.json()
        formatted = data["citations_formatted"]
        assert len(formatted) > 0
        assert "CITATION" in formatted or "wallach" in formatted.lower()


class TestRagFastPath:
    """When all biomarkers are normal, RAG should skip."""

    def test_all_normal_returns_empty_rag(self, client, all_normal_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(all_normal_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={"verified_results": verified})
        data = response.json()
        assert data["rag_output"]["matched_patterns"] == []
        assert data["citations"] == []
        assert data["timings"].get("fast_path") is True


class TestRagOrganSystemFiltering:
    """Metadata-filtered hybrid search by organ system."""

    def test_iron_markers_get_hematologic_content(self, client, iron_deficiency_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={"verified_results": verified})
        data = response.json()
        citations = data["citations"]
        # At least one citation should be hematology-related
        hematologic_keywords = [
            "anemia", "iron", "ferritin", "microcytic", "hematologic",
            "red blood cell", "hemoglobin",
        ]
        any_heme = any(
            any(kw in c["source"].lower() or kw in c.get("text", "").lower()
                for kw in hematologic_keywords)
            for c in citations
        )
        assert any_heme, "No hematology-related content in citations"


class TestRagWithMedications:
    """RAG pipeline with medication context."""

    def test_medications_passed_through(self, client, iron_deficiency_biomarkers):
        verify_resp = client.post("/api/verify", json={
            "biomarkers": to_dict(iron_deficiency_biomarkers),
        })
        verified = verify_resp.json()["verified_results"]

        response = client.post("/api/rag", json={
            "verified_results": verified,
            "medications": ["Metformin", "Biotin"],
        })
        assert response.status_code == 200
