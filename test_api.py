"""Tests for the FastAPI application.

Uses synthetic raster files from conftest.py.  No real satellite data
is uploaded or processed during tests.  The TestClient communicates
with an in-process app instance (no network required).
"""
from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from guardian.api.main import create_app


# ── App fixture ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Module-scoped TestClient with a fresh app instance.

    The ``with`` context manager triggers the lifespan, which initialises
    ``app.state.jobs``.  Module scope means job state persists across tests
    in this file (necessary for the download tests).
    """
    app = create_app()
    with TestClient(app) as c:
        yield c


# ── GET /health ───────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_status_200(self, client: TestClient) -> None:
        assert client.get("/health").status_code == 200

    def test_status_is_ok(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_version_present(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_service_name_present(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert "service" in data


# ── POST /analyze ─────────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    def _upload(
        self, client: TestClient, pre_path: Path, post_path: Path
    ) -> dict:
        with open(pre_path, "rb") as fp, open(post_path, "rb") as fq:
            resp = client.post(
                "/analyze",
                files={
                    "pre_flood": ("pre.tif", fp, "image/tiff"),
                    "post_flood": ("post.tif", fq, "image/tiff"),
                },
            )
        return resp

    def test_valid_upload_200(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        resp = self._upload(client, pre_flood_path, post_flood_path)
        assert resp.status_code == 200, resp.text

    def test_response_has_required_keys(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        data = self._upload(client, pre_flood_path, post_flood_path).json()
        for key in (
            "job_id",
            "flooded_pixel_count",
            "valid_pixel_count",
            "flooded_fraction",
            "flood_geotiff_url",
            "flood_geojson_url",
        ):
            assert key in data, f"Missing key: {key}"

    def test_correct_flood_count(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        data = self._upload(client, pre_flood_path, post_flood_path).json()
        assert data["flooded_pixel_count"] == 25

    def test_flooded_fraction_is_float(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        data = self._upload(client, pre_flood_path, post_flood_path).json()
        assert isinstance(data["flooded_fraction"], float)
        assert 0.0 <= data["flooded_fraction"] <= 1.0

    def test_missing_post_flood_422(
        self, client: TestClient, pre_flood_path: Path
    ) -> None:
        with open(pre_flood_path, "rb") as fp:
            resp = client.post(
                "/analyze",
                files={"pre_flood": ("pre.tif", fp, "image/tiff")},
            )
        assert resp.status_code == 422

    def test_missing_both_files_422(self, client: TestClient) -> None:
        assert client.post("/analyze").status_code == 422

    def test_misaligned_rasters_422(
        self, client: TestClient, pre_flood_path: Path, mismatched_shape_path: Path
    ) -> None:
        with open(pre_flood_path, "rb") as fp, open(mismatched_shape_path, "rb") as fq:
            resp = client.post(
                "/analyze",
                files={
                    "pre_flood": ("pre.tif", fp, "image/tiff"),
                    "post_flood": ("mis.tif", fq, "image/tiff"),
                },
            )
        assert resp.status_code == 422

    def test_urls_point_to_results(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        data = self._upload(client, pre_flood_path, post_flood_path).json()
        job_id = data["job_id"]
        assert data["flood_geotiff_url"] == f"/results/{job_id}/flood.tif"
        assert data["flood_geojson_url"] == f"/results/{job_id}/flood.geojson"


# ── GET /results/{job_id}/{filename} ─────────────────────────────────────

class TestResultsEndpoint:
    def _run_analysis(
        self, client: TestClient, pre_path: Path, post_path: Path
    ) -> str:
        with open(pre_path, "rb") as fp, open(post_path, "rb") as fq:
            resp = client.post(
                "/analyze",
                files={
                    "pre_flood": ("pre.tif", fp, "image/tiff"),
                    "post_flood": ("post.tif", fq, "image/tiff"),
                },
            )
        assert resp.status_code == 200
        return resp.json()["job_id"]

    def test_download_geotiff_200(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        job_id = self._run_analysis(client, pre_flood_path, post_flood_path)
        resp = client.get(f"/results/{job_id}/flood.tif")
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_download_geojson_200(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        job_id = self._run_analysis(client, pre_flood_path, post_flood_path)
        resp = client.get(f"/results/{job_id}/flood.geojson")
        assert resp.status_code == 200

    def test_geotiff_content_is_binary(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        job_id = self._run_analysis(client, pre_flood_path, post_flood_path)
        resp = client.get(f"/results/{job_id}/flood.tif")
        # A valid GeoTIFF starts with the TIFF magic bytes (II or MM)
        assert resp.content[:2] in (b"II", b"MM"), (
            "Response body does not look like a TIFF file"
        )

    def test_unknown_job_404(self, client: TestClient) -> None:
        resp = client.get("/results/00000000-0000-0000-0000-000000000000/flood.tif")
        assert resp.status_code == 404

    def test_disallowed_filename_404(
        self, client: TestClient, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """Filename not in allowlist returns 404 (path-traversal protection)."""
        job_id = self._run_analysis(client, pre_flood_path, post_flood_path)
        resp = client.get(f"/results/{job_id}/other_file.txt")
        assert resp.status_code == 404
