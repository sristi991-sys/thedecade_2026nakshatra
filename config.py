"""Central configuration and constants for Guardian of the Terai.

All tuneable parameters and shared constants live here.  Import from
this module rather than hardcoding values in sub-modules.

Environment variables
---------------------
GUARDIAN_RESULTS_DIR
    Directory where analysis job outputs (GeoTIFF, GeoJSON) are stored.
    Defaults to ``./results`` relative to the working directory.
    Setting this at test time keeps generated files out of the workspace.
"""
from __future__ import annotations

import os

# ── Project metadata ──────────────────────────────────────────────────────
VERSION: str = "0.1.0"
PROJECT_NAME: str = "Guardian of the Terai"

# ── Flood detection parameters ────────────────────────────────────────────
#: Default backscatter change threshold (dB).
#: Pixels where Δ = σ°_post(dB) − σ°_pre(dB) < threshold are classified
#: as flooded.  −3 dB is a widely used heuristic from ESA/DLR literature.
DEFAULT_THRESHOLD_DB: float = -3.0

#: Minimum connected-component size (pixels) retained after thresholding.
#: Smaller components are assumed to be speckle noise and removed.
MIN_AREA_PIXELS: int = 9

# ── Output encoding ───────────────────────────────────────────────────────
#: uint8 value used to flag nodata / invalid pixels in output GeoTIFFs.
#: 0 = valid & not flooded, 1 = flooded, 255 = nodata/invalid.
NODATA_OUT: int = 255


def get_results_dir() -> "Path":  # type: ignore[name-defined]  # noqa: F821
    """Return the results directory, re-reading the environment each call.

    This function is deliberately not cached so that setting
    ``GUARDIAN_RESULTS_DIR`` at test-fixture time takes effect without
    requiring module reloads.
    """
    from pathlib import Path
    return Path(os.getenv("GUARDIAN_RESULTS_DIR", "results"))
