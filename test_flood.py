"""Tests for guardian.detection.flood.

Inputs are synthetic rasters from conftest.py.  These tests verify
detection logic, not real flood observations.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from guardian.detection.flood import FloodResult, detect_flood
from guardian.preprocessing.sentinel import AlignmentError, ScaleHint, ValidationError
from tests.conftest import FLOODED_PIXEL_COUNT  # 25 — known value for 5×5 region


class TestDetectFlood:
    # ── Return type ───────────────────────────────────────────────────────
    def test_returns_flood_result(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        result = detect_flood(pre_flood_path, post_flood_path)
        assert isinstance(result, FloodResult)

    # ── Pixel counts ──────────────────────────────────────────────────────
    def test_flooded_pixel_count(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """Flooded pixels == known 5×5 synthetic region (25 px)."""
        result = detect_flood(pre_flood_path, post_flood_path)
        assert result.flooded_pixel_count == FLOODED_PIXEL_COUNT, (
            f"Expected {FLOODED_PIXEL_COUNT}, got {result.flooded_pixel_count}"
        )

    def test_valid_pixel_count_no_nodata(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """All 400 pixels valid when neither scene has nodata."""
        result = detect_flood(pre_flood_path, post_flood_path)
        assert result.valid_pixel_count == 20 * 20

    def test_flooded_fraction(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        result = detect_flood(pre_flood_path, post_flood_path)
        assert result.flooded_fraction == pytest.approx(25 / 400, rel=1e-4)

    # ── Mask geometry ─────────────────────────────────────────────────────
    def test_mask_shapes(self, pre_flood_path: Path, post_flood_path: Path) -> None:
        result = detect_flood(pre_flood_path, post_flood_path)
        assert result.flood_mask.shape == (20, 20)
        assert result.valid_mask.shape == (20, 20)

    def test_flood_mask_is_bool(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        result = detect_flood(pre_flood_path, post_flood_path)
        assert result.flood_mask.dtype == bool

    def test_flooded_region_location(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """Flooded pixels must be in the top-left 5×5 region, nowhere else."""
        result = detect_flood(pre_flood_path, post_flood_path)
        assert np.all(result.flood_mask[0:5, 0:5]), (
            "Top-left 5×5 must all be flooded"
        )
        assert not np.any(result.flood_mask[5:, :]), (
            "Pixels below row 5 must not be flooded"
        )
        assert not np.any(result.flood_mask[:, 5:]), (
            "Pixels right of col 5 must not be flooded"
        )

    def test_flood_mask_subset_of_valid(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """flood_mask must always be a subset of valid_mask."""
        result = detect_flood(pre_flood_path, post_flood_path)
        # Wherever flooded, must also be valid
        invalid_and_flooded = result.flood_mask & ~result.valid_mask
        assert not np.any(invalid_and_flooded), (
            "Flooded pixels must also be valid"
        )

    # ── Nodata handling ───────────────────────────────────────────────────
    def test_nodata_excluded_from_valid(
        self, pre_with_nodata_path: Path, post_with_nodata_path: Path
    ) -> None:
        """Last row is nodata in both scenes → 380 valid pixels."""
        result = detect_flood(pre_with_nodata_path, post_with_nodata_path)
        assert result.valid_pixel_count == 20 * 19  # 380

    def test_nodata_excluded_from_flood_count(
        self, pre_with_nodata_path: Path, post_with_nodata_path: Path
    ) -> None:
        """Flooded region does not overlap with nodata row → count unchanged."""
        result = detect_flood(pre_with_nodata_path, post_with_nodata_path)
        assert result.flooded_pixel_count == FLOODED_PIXEL_COUNT

    def test_nodata_row_not_flooded(
        self, pre_with_nodata_path: Path, post_with_nodata_path: Path
    ) -> None:
        result = detect_flood(pre_with_nodata_path, post_with_nodata_path)
        assert not np.any(result.flood_mask[-1, :]), (
            "Nodata row (last) must not be classified as flooded"
        )
        assert not np.any(result.valid_mask[-1, :]), (
            "Nodata row must not be valid"
        )

    # ── Threshold sensitivity ─────────────────────────────────────────────
    def test_strict_threshold_zero_flood(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """Threshold −6 dB: Δ (−5 dB) is not < −6, so 0 flooded pixels."""
        result = detect_flood(pre_flood_path, post_flood_path, threshold_db=-6.0)
        assert result.flooded_pixel_count == 0

    def test_lenient_threshold_full_flood(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        """Threshold −1 dB: Δ (−5 dB) is < −1, so flooded region detected."""
        result = detect_flood(pre_flood_path, post_flood_path, threshold_db=-1.0)
        assert result.flooded_pixel_count == FLOODED_PIXEL_COUNT

    # ── Provenance fields ─────────────────────────────────────────────────
    def test_threshold_recorded(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        result = detect_flood(pre_flood_path, post_flood_path, threshold_db=-5.0)
        assert result.threshold_db == -5.0

    def test_scale_recorded(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        result = detect_flood(pre_flood_path, post_flood_path, scale=ScaleHint.DB)
        assert result.scale_used is ScaleHint.DB

    def test_meta_has_crs_and_transform(
        self, pre_flood_path: Path, post_flood_path: Path
    ) -> None:
        result = detect_flood(pre_flood_path, post_flood_path)
        assert "crs" in result.meta
        assert "transform" in result.meta

    # ── Error cases ───────────────────────────────────────────────────────
    def test_missing_pre_raises(
        self, tmp_path: Path, post_flood_path: Path
    ) -> None:
        with pytest.raises(ValidationError):
            detect_flood(tmp_path / "nonexistent.tif", post_flood_path)

    def test_misaligned_raises(
        self, pre_flood_path: Path, mismatched_shape_path: Path
    ) -> None:
        with pytest.raises(AlignmentError):
            detect_flood(pre_flood_path, mismatched_shape_path)
