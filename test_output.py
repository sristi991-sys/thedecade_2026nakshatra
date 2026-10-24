"""Tests for guardian.output.geotiff and guardian.output.geojson.

FloodResult objects are constructed directly (no upstream file I/O)
to keep output tests isolated from the detection module.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from guardian.config import NODATA_OUT
from guardian.detection.flood import FloodResult
from guardian.output.geojson import write_flood_geojson
from guardian.output.geotiff import write_flood_geotiff
from guardian.preprocessing.sentinel import ScaleHint


# ── Synthetic FloodResult factory ──────────────────────────────────────────

def _make_result(
    height: int = 10,
    width: int = 10,
    flood_rows: slice = slice(0, 3),
    flood_cols: slice = slice(0, 3),
) -> FloodResult:
    """Build a synthetic FloodResult with a rectangular flooded region."""
    crs = CRS.from_epsg(4326)
    transform = from_bounds(83.0, 27.0, 85.0, 29.0, width, height)

    flood_mask = np.zeros((height, width), dtype=bool)
    flood_mask[flood_rows, flood_cols] = True  # 3×3 = 9 flooded pixels

    valid_mask = np.ones((height, width), dtype=bool)

    meta = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": crs,
        "transform": transform,
        "nodata": -9999.0,
    }
    flooded = int(np.sum(flood_mask))
    valid = int(np.sum(valid_mask))

    return FloodResult(
        flood_mask=flood_mask,
        valid_mask=valid_mask,
        meta=meta,
        flooded_pixel_count=flooded,
        valid_pixel_count=valid,
        flooded_fraction=flooded / valid,
        threshold_db=-3.0,
        scale_used=ScaleHint.DB,
    )


# ── GeoTIFF output tests ───────────────────────────────────────────────────

class TestWriteFloodGeoTiff:
    def test_file_created(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        assert out.exists()

    def test_flooded_pixels_encoded_as_1(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        result = _make_result()
        write_flood_geotiff(result, out)
        with rasterio.open(out) as ds:
            arr = ds.read(1)
        assert np.all(arr[0:3, 0:3] == 1), "Flooded region must be encoded as 1"

    def test_dry_pixels_encoded_as_0(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        with rasterio.open(out) as ds:
            arr = ds.read(1)
        assert np.all(arr[3:, 3:] == 0), "Non-flooded valid pixels must be encoded as 0"

    def test_invalid_pixels_encoded_as_nodata(self, tmp_path: Path) -> None:
        result = _make_result()
        result.valid_mask[9, 9] = False   # mark corner invalid
        result.flood_mask[9, 9] = False   # can't be flooded if invalid
        out = tmp_path / "flood_inv.tif"
        write_flood_geotiff(result, out)
        with rasterio.open(out) as ds:
            arr = ds.read(1)
        assert arr[9, 9] == NODATA_OUT, (
            f"Invalid pixel must be {NODATA_OUT}, got {arr[9, 9]}"
        )

    def test_nodata_value_in_profile(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        with rasterio.open(out) as ds:
            assert ds.nodata == NODATA_OUT

    def test_crs_preserved(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        with rasterio.open(out) as ds:
            assert ds.crs is not None
            assert ds.crs.to_epsg() == 4326

    def test_dtype_is_uint8(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        with rasterio.open(out) as ds:
            assert ds.dtypes[0] == "uint8"

    def test_single_band(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        with rasterio.open(out) as ds:
            assert ds.count == 1

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "a" / "b" / "flood.tif"
        write_flood_geotiff(_make_result(), out)
        assert out.exists()

    def test_no_flood_all_zeros(self, tmp_path: Path) -> None:
        """When nothing is flooded, all valid pixels are 0."""
        result = _make_result()
        result.flood_mask[:] = False
        result.flooded_pixel_count = 0
        out = tmp_path / "no_flood.tif"
        write_flood_geotiff(result, out)
        with rasterio.open(out) as ds:
            arr = ds.read(1)
        # All valid pixels should be 0
        assert np.all(arr[result.valid_mask] == 0)


# ── GeoJSON output tests ───────────────────────────────────────────────────

class TestWriteFloodGeoJson:
    def test_file_created(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.geojson"
        write_flood_geojson(_make_result(), out)
        assert out.exists()

    def test_valid_json(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.geojson"
        write_flood_geojson(_make_result(), out)
        with open(out) as fh:
            data = json.load(fh)
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_has_flooded_features(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.geojson"
        write_flood_geojson(_make_result(), out)
        with open(out) as fh:
            data = json.load(fh)
        assert len(data["features"]) >= 1, "Must have at least one feature when pixels are flooded"

    def test_flooded_property_is_true(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.geojson"
        write_flood_geojson(_make_result(), out)
        with open(out) as fh:
            data = json.load(fh)
        for feat in data["features"]:
            assert feat["properties"]["flooded"] is True

    def test_geometry_type(self, tmp_path: Path) -> None:
        out = tmp_path / "flood.geojson"
        write_flood_geojson(_make_result(), out)
        with open(out) as fh:
            data = json.load(fh)
        for feat in data["features"]:
            assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")

    def test_empty_when_no_flood(self, tmp_path: Path) -> None:
        result = _make_result()
        result.flood_mask[:] = False
        result.flooded_pixel_count = 0
        out = tmp_path / "empty.geojson"
        write_flood_geojson(result, out)
        with open(out) as fh:
            data = json.load(fh)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 0

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "flood.geojson"
        write_flood_geojson(_make_result(), out)
        assert out.exists()
