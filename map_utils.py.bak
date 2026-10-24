"""Folium map helper utilities for the Streamlit dashboard.

This module is a **presentation layer** only.  It does not perform any
flood detection or raster analysis.  All map data originates from the
Guardian API.
"""
from __future__ import annotations

from typing import Any

import folium

# ── Default map centre: Nepal's Terai belt (Chitwan / Narayani basin) ──────
_DEFAULT_LAT: float = 27.5
_DEFAULT_LON: float = 84.0
_DEFAULT_ZOOM: int = 8

# ── Flood polygon visual style ─────────────────────────────────────────────
_FLOOD_STYLE: dict = {
    "fillColor": "#1565C0",  # deep blue (water)
    "color": "#0D47A1",
    "weight": 1.5,
    "fillOpacity": 0.55,
}


def create_base_map(
    lat: float = _DEFAULT_LAT,
    lon: float = _DEFAULT_LON,
    zoom: int = _DEFAULT_ZOOM,
) -> folium.Map:
    """Create a Folium map centred on Nepal's Terai region.

    Parameters
    ----------
    lat, lon:
        Map centre in decimal degrees (WGS 84).
    zoom:
        Initial zoom level (0–18).

    Returns
    -------
    folium.Map
    """
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
    )
    folium.LayerControl().add_to(m)
    return m


def add_flood_geojson(m: folium.Map, geojson_data: dict[str, Any]) -> folium.Map:
    """Overlay a flood GeoJSON FeatureCollection on a Folium map.

    Parameters
    ----------
    m:
        Existing Folium map to augment (modified in-place).
    geojson_data:
        A GeoJSON ``FeatureCollection`` dict produced by the Guardian API.
        Features must have ``{"flooded": true}`` in their properties.

    Returns
    -------
    folium.Map
        The same map with the flood layer added.  Returns unmodified
        map if ``geojson_data`` contains no features.
    """
    if not geojson_data.get("features"):
        return m

    layer = folium.GeoJson(
        geojson_data,
        name="Flood extent",
        style_function=lambda _: _FLOOD_STYLE,
        tooltip=folium.GeoJsonTooltip(
            fields=["flooded"],
            aliases=["Flooded:"],
            localize=True,
        ),
    )
    layer.add_to(m)

    # Zoom map to the flood extent
    try:
        bounds = layer.get_bounds()
        if bounds and bounds[0] != bounds[1]:
            m.fit_bounds(bounds, padding=(20, 20))
    except Exception:
        pass  # Non-fatal; default zoom is used as fallback

    return m
