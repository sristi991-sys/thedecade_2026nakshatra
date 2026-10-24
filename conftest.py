"""Shared pytest fixtures for Guardian of the Terai tests.

IMPORTANT
---------
All rasters generated in this module are **synthetic** (numpy arrays with
controlled values).  They do NOT represent actual Sentinel-1 observations
or real flood events.  They exist solely to exercise software logic.

Spatial metadata (CRS, bounding box) uses plausible Terai coordinates
purely as metadata; pixel values are hand-crafted for deterministic tests.

Environment variable
--------------------
``GUARDIAN_RESULTS_DIR`` is redirected to a session-scoped temp directory
so that API test jobs do not create files in the workspace.  The redirect
is applied before any test imports the analysis module.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds, from_origin

# ── Synthetic raster parameters ───────────────────────────────────────────
# Plausible Terai bounding box (metadata only; pixels are synthetic).
_WEST, _SOUTH, _EAST, _NORTH = 83.0, 27.0, 85.0, 29.0
_WIDTH, _HEIGHT = 20, 20
_CRS = CRS.from_epsg(4326)
_TRANSFORM = from_bounds(_WEST, _SOUTH, _EAST, _NORTH, _WIDTH, _HEIGHT)
_NODATA: float = -9999.0

# dB values chosen so the flooded region gives Δ = −5 dB (< −3 dB threshold)
_PRE_DB: float = -10.0    # dry-land background
_DRY_DB: float = -10.0    # unchanged post-flood pixels
_WET_DB: float = -15.0    # flooded pixels (Δ = WET − PRE = −5 dB)

# Flooded region: top-left 5 × 5 pixels → 25 flooded pixels
_FLOOD_R, _FLOOD_C = 5, 5
FLOODED_PIXEL_COUNT: int = _FLOOD_R * _FLOOD_C   # 25 — importable by tests


# ── Internal helper ───────────────────────────────────────────────────────

def _write_raster(
    path: Path,
    data: np.ndarray,
    crs: CRS = _CRS,
    transform=_TRANSFORM,
    nodata: float | None = _NODATA,
) -> None:
    """Write a 2D float32 array as a single-band GeoTIFF."""
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": data.shape[1],
        "height": data.shape[0],
        "count": 1,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(data.astype(np.float32), 1)


# ── Session-scoped temp directory for rasters ─────────────────────────────

@pytest.fixture(scope="session")
def raster_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped temp directory for synthetic raster files."""
    return tmp_path_factory.mktemp("rasters")


# ── Redirect GUARDIAN_RESULTS_DIR for API tests ────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def redirect_results_dir(tmp_path_factory: pytest.TempPathFactory) -> Generator:
    """Set GUARDIAN_RESULTS_DIR to a temp dir for the whole test session.

    Because ``guardian.config.get_results_dir()`` reads the env var at
    call time, setting it here is sufficient — no module reloads required.
    """
    td = tmp_path_factory.mktemp("guardian_results")
    os.environ["GUARDIAN_RESULTS_DIR"] = str(td)
    yield td
    # Clean up env so subsequent processes are not affected
    os.environ.pop("GUARDIAN_RESULTS_DIR", None)


# ── Base synthetic rasters ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pre_flood_path(raster_dir: Path) -> Path:
    """Synthetic pre-flood GeoTIFF: uniform −10 dB (dry land)."""
    path = raster_dir / "pre_flood.tif"
    data = np.full((_HEIGHT, _WIDTH), _PRE_DB, dtype=np.float32)
    _write_raster(path, data)
    return path


@pytest.fixture(scope="session")
def post_flood_path(raster_dir: Path) -> Path:
    """Synthetic post-flood GeoTIFF: top-left 5×5 at −15 dB (Δ = −5 dB)."""
    path = raster_dir / "post_flood.tif"
    data = np.full((_HEIGHT, _WIDTH), _DRY_DB, dtype=np.float32)
    data[0:_FLOOD_R, 0:_FLOOD_C] = _WET_DB
    _write_raster(path, data)
    return path


# ── Nodata fixtures ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pre_with_nodata_path(raster_dir: Path) -> Path:
    """Pre-flood GeoTIFF: last row set to nodata (−9999)."""
    path = raster_dir / "pre_nodata.tif"
    data = np.full((_HEIGHT, _WIDTH), _PRE_DB, dtype=np.float32)
    data[-1, :] = _NODATA
    _write_raster(path, data)
    return path


@pytest.fixture(scope="session")
def post_with_nodata_path(raster_dir: Path) -> Path:
    """Post-flood GeoTIFF with flooded region + last row nodata."""
    path = raster_dir / "post_nodata.tif"
    data = np.full((_HEIGHT, _WIDTH), _DRY_DB, dtype=np.float32)
    data[0:_FLOOD_R, 0:_FLOOD_C] = _WET_DB
    data[-1, :] = _NODATA
    _write_raster(path, data)
    return path


# ── Misaligned fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mismatched_shape_path(raster_dir: Path) -> Path:
    """GeoTIFF with different pixel dimensions (5×5 instead of 20×20)."""
    path = raster_dir / "mismatched_shape.tif"
    wrong_transform = from_bounds(_WEST, _SOUTH, _EAST, _NORTH, width=5, height=5)
    data = np.full((5, 5), _PRE_DB, dtype=np.float32)
    _write_raster(path, data, transform=wrong_transform)
    return path


@pytest.fixture(scope="session")
def mismatched_crs_path(raster_dir: Path) -> Path:
    """GeoTIFF with a different CRS (EPSG:32645 — UTM zone 45N)."""
    path = raster_dir / "wrong_crs.tif"
    wrong_crs = CRS.from_epsg(32645)
    # Approximate UTM coordinates for the Terai region
    wrong_transform = from_origin(700_000, 3_200_000, 200, 200)
    data = np.full((_HEIGHT, _WIDTH), _PRE_DB, dtype=np.float32)
    _write_raster(path, data, crs=wrong_crs, transform=wrong_transform)
    return path
