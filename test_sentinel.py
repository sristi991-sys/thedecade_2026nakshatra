"""Tests for guardian.preprocessing.sentinel.

All rasters are synthetic.  See tests/conftest.py.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from guardian.preprocessing.sentinel import (
    AlignmentError,
    ScaleHint,
    ValidationError,
    align_rasters,
    load_band,
    validate_geotiff,
)


# ── validate_geotiff ──────────────────────────────────────────────────────

class TestValidateGeoTiff:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="[Nn]ot found"):
            validate_geotiff(tmp_path / "ghost.tif")

    def test_non_raster_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "text.txt"
        bad.write_text("not a raster")
        with pytest.raises(ValidationError):
            validate_geotiff(bad)

    def test_valid_geotiff_returns_meta(self, pre_flood_path: Path) -> None:
        meta = validate_geotiff(pre_flood_path)
        assert meta.crs is not None
        assert meta.width == 20
        assert meta.height == 20
        assert meta.count >= 1

    def test_crs_is_epsg4326(self, pre_flood_path: Path) -> None:
        meta = validate_geotiff(pre_flood_path)
        assert meta.crs.to_epsg() == 4326

    def test_nodata_recorded(self, pre_flood_path: Path) -> None:
        meta = validate_geotiff(pre_flood_path)
        assert meta.nodata == pytest.approx(-9999.0)

    def test_path_normalised(self, pre_flood_path: Path) -> None:
        meta = validate_geotiff(str(pre_flood_path))  # str input
        assert isinstance(meta.path, Path)


# ── load_band ─────────────────────────────────────────────────────────────

class TestLoadBand:
    def test_shape(self, pre_flood_path: Path) -> None:
        arr = load_band(pre_flood_path, scale=ScaleHint.DB)
        assert arr.shape == (20, 20)

    def test_dtype_is_float32(self, pre_flood_path: Path) -> None:
        arr = load_band(pre_flood_path, scale=ScaleHint.DB)
        assert arr.dtype == np.float32

    def test_returns_masked_array(self, pre_flood_path: Path) -> None:
        arr = load_band(pre_flood_path, scale=ScaleHint.DB)
        assert isinstance(arr, np.ma.MaskedArray)

    def test_nodata_pixels_are_masked(self, pre_with_nodata_path: Path) -> None:
        arr = load_band(pre_with_nodata_path, scale=ScaleHint.DB)
        mask = np.ma.getmaskarray(arr)
        # Last row must be fully masked
        assert np.all(mask[-1, :]), "Last row (nodata) should be masked"
        # All other rows should be unmasked
        assert not np.any(mask[:-1, :]), "Non-nodata rows should not be masked"

    def test_linear_converts_to_db(self, tmp_path: Path) -> None:
        """0.01 linear power → 10 * log10(0.01) = −20 dB."""
        crs = CRS.from_epsg(4326)
        transform = from_bounds(83.0, 27.0, 85.0, 29.0, width=5, height=5)
        profile = {
            "driver": "GTiff", "dtype": "float32",
            "width": 5, "height": 5, "count": 1,
            "crs": crs, "transform": transform, "nodata": None,
        }
        data = np.full((5, 5), 0.01, dtype=np.float32)
        path = tmp_path / "linear.tif"
        with rasterio.open(path, "w", **profile) as ds:
            ds.write(data, 1)

        result = load_band(path, scale=ScaleHint.LINEAR)
        expected_db = 10.0 * np.log10(0.01)  # ≈ −20 dB
        assert np.allclose(result.compressed(), expected_db, atol=0.05), (
            f"Expected ≈{expected_db:.2f} dB, got {float(result.mean()):.2f}"
        )

    def test_linear_masks_zero(self, tmp_path: Path) -> None:
        crs = CRS.from_epsg(4326)
        transform = from_bounds(83.0, 27.0, 85.0, 29.0, width=3, height=3)
        profile = {
            "driver": "GTiff", "dtype": "float32",
            "width": 3, "height": 3, "count": 1,
            "crs": crs, "transform": transform, "nodata": None,
        }
        data = np.full((3, 3), 0.5, dtype=np.float32)
        data[0, 0] = 0.0    # zero → must be masked
        data[0, 1] = -0.1   # negative → must be masked
        path = tmp_path / "linear_zero.tif"
        with rasterio.open(path, "w", **profile) as ds:
            ds.write(data, 1)

        result = load_band(path, scale=ScaleHint.LINEAR)
        mask = np.ma.getmaskarray(result)
        assert mask[0, 0], "Zero linear value must be masked"
        assert mask[0, 1], "Negative linear value must be masked"
        assert not mask[1, 0], "Positive linear value must not be masked"

    def test_invalid_band_number_raises(self, pre_flood_path: Path) -> None:
        with pytest.raises(ValidationError, match="[Bb]and"):
            load_band(pre_flood_path, band=99, scale=ScaleHint.DB)

    def test_scale_hint_db_does_not_convert(self, pre_flood_path: Path) -> None:
        """ScaleHint.DB must NOT apply any log conversion."""
        arr = load_band(pre_flood_path, scale=ScaleHint.DB)
        # Pre-flood values are −10 dB; if wrongly converted they'd differ
        valid_vals = arr.compressed()
        assert np.allclose(valid_vals, -10.0, atol=0.01), (
            "DB scale should preserve values as-is"
        )


# ── align_rasters ─────────────────────────────────────────────────────────

class TestAlignRasters:
    def test_aligned_pair_passes(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        pre_m, post_m = align_rasters(pre_flood_path, post_flood_path)
        assert pre_m.crs == post_m.crs
        assert (pre_m.width, pre_m.height) == (post_m.width, post_m.height)

    def test_crs_mismatch_raises(
        self, pre_flood_path: Path, mismatched_crs_path: Path
    ) -> None:
        with pytest.raises(AlignmentError, match="CRS"):
            align_rasters(pre_flood_path, mismatched_crs_path)

    def test_shape_mismatch_raises(
        self, pre_flood_path: Path, mismatched_shape_path: Path
    ) -> None:
        with pytest.raises(AlignmentError, match="[Ss]hape|mismatch"):
            align_rasters(pre_flood_path, mismatched_shape_path)

    def test_missing_file_raises_validation(self, tmp_path: Path, post_flood_path: Path) -> None:
        with pytest.raises(ValidationError):
            align_rasters(tmp_path / "ghost.tif", post_flood_path)

    def test_error_message_lists_all_mismatches(
        self, pre_flood_path: Path, mismatched_crs_path: Path
    ) -> None:
        """AlignmentError message should detail each mismatch found."""
        with pytest.raises(AlignmentError) as exc_info:
            align_rasters(pre_flood_path, mismatched_crs_path)
        msg = str(exc_info.value)
        assert "mismatch" in msg.lower()
