"""
Tests for POST /api/ocr — OCR Pipeline (Module 1).

Covers: file upload, PDF/image processing, biomarker extraction,
response structure, error handling.
"""

import os
import pytest
from pathlib import Path


BACKEND_DIR = Path(__file__).parent.parent / "backend"


def _pdf_path(filename: str) -> Path:
    return BACKEND_DIR / filename


class TestOcrEndpoint:
    """POST /api/ocr — endpoint behavior."""

    @pytest.mark.skipif(
        not _pdf_path("report5.pdf").exists(),
        reason="No test PDF available in backend/",
    )
    def test_pdf_upload_returns_200(self, client):
        pdf_path = _pdf_path("report5.pdf")
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/ocr",
                files={"file": ("report5.pdf", f, "application/pdf")},
            )
        assert response.status_code == 200
        data = response.json()
        assert "biomarkers" in data
        assert "raw_text" in data
        assert "parse_confidence" in data

    def test_invalid_extension_returns_400(self, client):
        response = client.post(
            "/api/ocr",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert response.status_code == 400

    def test_no_file_returns_422(self, client):
        response = client.post("/api/ocr")
        assert response.status_code == 422


class TestOcrResponseStructure:
    """Validate OCR response shape."""

    @pytest.mark.skipif(
        not _pdf_path("report5.pdf").exists(),
        reason="No test PDF available in backend/",
    )
    def test_biomarkers_have_required_fields(self, client):
        pdf_path = _pdf_path("report5.pdf")
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/ocr",
                files={"file": ("report5.pdf", f, "application/pdf")},
            )
        assert response.status_code == 200
        data = response.json()
        for b in data["biomarkers"]:
            assert "name" in b
            assert "value" in b
            assert "unit" in b
            assert "ref_low" in b
            assert "ref_high" in b
            assert "flag" in b
            assert isinstance(b["value"], (int, float))

    @pytest.mark.skipif(
        not _pdf_path("report5.pdf").exists(),
        reason="No test PDF available in backend/",
    )
    def test_parse_confidence_is_between_0_and_1(self, client):
        pdf_path = _pdf_path("report5.pdf")
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/ocr",
                files={"file": ("report5.pdf", f, "application/pdf")},
            )
        data = response.json()
        assert 0 <= data["parse_confidence"] <= 1

    @pytest.mark.skipif(
        not _pdf_path("report5.pdf").exists(),
        reason="No test PDF available in backend/",
    )
    def test_raw_text_is_not_empty(self, client):
        pdf_path = _pdf_path("report5.pdf")
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/ocr",
                files={"file": ("report5.pdf", f, "application/pdf")},
            )
        data = response.json()
        assert len(data["raw_text"]) > 0


class TestOcrBiomarkerFlags:
    """Verify OCR correctly assigns H/L flags based on reference ranges."""

    @pytest.mark.skipif(
        not _pdf_path("report5.pdf").exists(),
        reason="No test PDF available in backend/",
    )
    def test_some_biomarkers_have_flags(self, client):
        pdf_path = _pdf_path("report5.pdf")
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/ocr",
                files={"file": ("report5.pdf", f, "application/pdf")},
            )
        data = response.json()
        flags = [b["flag"] for b in data["biomarkers"] if b["flag"] is not None]
        # At least some biomarkers should have flags (H or L)
        assert len(flags) >= 1
        assert all(f in ("H", "L") for f in flags)
