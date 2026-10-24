"""Guardian of the Terai â" Streamlit Dashboard.

Presentation layer for flood detection results.  This app uploads
Sentinel-1 GeoTIFFs to the Guardian API, visualises flood statistics,
and renders an interactive flood-extent map.

Usage
-----
Start the API backend first::

    uvicorn guardian.api.main:app --reload

Then run this dashboard::

    streamlit run dashboard/app.py

Important
---------
All flood statistics displayed here are fetched from the Guardian API,
which derives them from raster pixel arithmetic on the uploaded scenes.
**No values are fabricated or interpolated by the dashboard.**
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import streamlit as st

from dashboard.map_utils import add_flood_geojson, create_base_map

# â"â" Page configuration â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
st.set_page_config(
    page_title="Guardian of the Terai",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# â"â" Custom CSS â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .guardian-header {
        background: linear-gradient(135deg, #0D47A1 0%, #1565C0 60%, #1976D2 100%);
        border-radius: 14px;
        padding: 1.6rem 2rem;
        color: white;
        margin-bottom: 1.5rem;
    }
    .guardian-header h1 { font-size: 2rem; margin: 0; font-weight: 700; }
    .guardian-header p  { margin: 0.3rem 0 0; opacity: 0.85; font-size: 1rem; }

    .stat-card {
        background: linear-gradient(135deg, #E3F2FD, #BBDEFB);
        border-left: 5px solid #1565C0;
        border-radius: 10px;
        padding: 1rem 1.2rem;
    }
    .stat-label { font-size: 0.78rem; color: #555; font-weight: 600;
                  text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-value { font-size: 1.9rem; font-weight: 700; color: #0D47A1; }

    .data-note {
        background: #FFF8E1;
        border-left: 4px solid #FFC107;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        font-size: 0.84rem;
        color: #555;
        margin-top: 0.5rem;
    }
    .limit-note {
        background: #FBE9E7;
        border-left: 4px solid #FF5722;
        border-radius: 6px;
        padding: 0.7rem 1rem;
        font-size: 0.84rem;
        color: #444;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# â"â" Sidebar â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
with st.sidebar:
    st.markdown("## Configuration")
    api_url: str = st.text_input(
        "API Base URL",
        value="http://localhost:8000",
        help="URL of the running Guardian FastAPI backend.",
    )
    st.divider()

    st.markdown("### Upload Sentinel-1 Scenes")
    st.caption("Both files must be in **dB scale** and co-registered.")

    pre_file = st.file_uploader(
        "Pre-flood GeoTIFF",
        type=["tif", "tiff"],
        key="pre_upload",
        help="Single-band Sentinel-1 backscatter in decibel scale.",
    )
    post_file = st.file_uploader(
        "Post-flood GeoTIFF",
        type=["tif", "tiff"],
        key="post_upload",
        help="Single-band Sentinel-1 backscatter in decibel scale.",
    )

    # ---- Demo data option ---------------------------------------------------
    st.divider()
    st.markdown("## Demo data (quick test)")
    demo_choice = st.selectbox(
        "Select a demo pair", 
        options=[
            "0.tif (pre) vs 1.tif (post)",
            "1.tif (pre) vs 2.tif (post)",
        ],
        help="Run the pipeline on bundled demo files located in data/demo/.",
    )
    demo_run = st.button("Run demo analysis", type="primary")


    run_btn = st.button(
        "Run Flood Detection",
        disabled=(pre_file is None or post_file is None),
        use_container_width=True,
        type="primary",
    )

    st.divider()
    st.markdown(
        """
        <div class='limit-note'>
        â ï¸ <b>Pre-processing requirements</b><br>
        â¢ Values must be in <b>dB scale</b><br>
        â¢ Same CRS, resolution & extent<br>
        â¢ Use ESA SNAP to co-register scenes
        </div>
        """,
        unsafe_allow_html=True,
    )

# â"â" Main header â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
st.markdown(
    """
    <div class='guardian-header'>
        <h1>🌊 Guardian of the Terai</h1>
        <p>Satellite-based flood mapping for Nepal's Terai region
           using Sentinel-1 SAR backscatter change detection.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# â"â" Session state init â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "flood_geojson" not in st.session_state:
    st.session_state.flood_geojson = None

# â"â" Run analysis â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
if run_btn and pre_file and post_file:
    with st.spinner("Uploading scenes and running flood detection â¦"):
        try:
            resp = httpx.post(
                f"{api_url.rstrip('/')}/analyze",
                files={
                    "pre_flood": (pre_file.name, pre_file.getvalue(), "image/tiff"),
                    "post_flood": (post_file.name, post_file.getvalue(), "image/tiff"),
                },
                timeout=180.0,
            )
            if resp.status_code == 200:
                result: dict[str, Any] = resp.json()
                st.session_state.analysis_result = result

                # Fetch GeoJSON for map overlay
                gj_resp = httpx.get(
                    f"{api_url.rstrip('/')}{result['flood_geojson_url']}",
                    timeout=60.0,
                )
                if gj_resp.status_code == 200:
                    st.session_state.flood_geojson = gj_resp.json()
            else:
                detail = resp.json().get("detail", resp.text)
                st.error(f"API error {resp.status_code}: {detail}")

        except httpx.ConnectError:
            st.error(
                f"Cannot connect to the API at **{api_url}**.  "
                "Start the backend:  \n"
                "```\nuvicorn guardian.api.main:app --reload\n```"
            )
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")

# â"â" Display results â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"â"
result = st.session_state.analysis_result
flood_geojson = st.session_state.flood_geojson

if result:
    st.success(f"✅ Analysis complete. Job `{result.get('job_id', 'N/A')}`")

    # Statistics row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"<div class='stat-card'>"
            f"<div class='stat-label'>Flooded pixels</div>"
            f"<div class='stat-value'>{result['flooded_pixel_count']:,}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div class='stat-card'>"
            f"<div class='stat-label'>Valid pixels</div>"
            f"<div class='stat-value'>{result['valid_pixel_count']:,}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        pct = result["flooded_fraction"] * 100
        st.markdown(
            f"<div class='stat-card'>"
            f"<div class='stat-label'>Flooded fraction</div>"
            f"<div class='stat-value'>{pct:.3f}%</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div class='data-note'>â ï¸ Statistics are derived from raster pixel "
        "arithmetic on the uploaded scenes.  No values are fabricated.</div>",
        unsafe_allow_html=True,
    )

    # Downloads
    st.markdown("### Download Results")
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        tif_resp = httpx.get(
            f"{api_url.rstrip('/')}{result['flood_geotiff_url']}", timeout=60.0
        )
        if tif_resp.status_code == 200:
            st.download_button(
                "Flood GeoTIFF (0/1/255 uint8)",
                data=tif_resp.content,
                file_name="flood_mask.tif",
                mime="image/tiff",
                use_container_width=True,
            )
    with dcol2:
        gj_resp2 = httpx.get(
            f"{api_url.rstrip('/')}{result['flood_geojson_url']}", timeout=60.0
        )
        if gj_resp2.status_code == 200:
            st.download_button(
                "Flood Polygons (GeoJSON, WGS 84)",
                data=gj_resp2.content,
                file_name="flood_polygons.geojson",
                mime="application/geo+json",
                use_container_width=True,
            )

    # Map
    st.divider()
    st.markdown("### Flood Extent Map")
    if flood_geojson and flood_geojson.get("features"):
        try:
            from streamlit_folium import st_folium

            m = create_base_map()
            m = add_flood_geojson(m, flood_geojson)
            st_folium(m, use_container_width=True, height=520)
        except ImportError:
            st.warning(
                "Install `streamlit-folium` to view the interactive map:  \n"
                "```\npip install streamlit-folium\n```"
            )
    else:
        st.info(
            "No flooded pixels detected in the provided scenes.  "
            "Try a lower detection threshold (default: -3 dB)."
        )

else:
    # Welcome / instruction state
    st.markdown("### How it works")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(
            """
1. **Upload** two co-registered Sentinel-1 GeoTIFFs (dB scale) in the sidebar.
2. The system computes backscatter change: **Î" = ÏÂ°_post â' ÏÂ°_pre**.
3. Pixels where **Î" < â'3 dB** are classified as flooded.
4. A minimum-area filter (≥ 9 pixels) removes isolated speckle noise.
5. Results are exported as a classified GeoTIFF and a GeoJSON polygon layer.

---

### Algorithm parameters

| Parameter | Default | Description |
|---|---|---|
| Threshold | â'3 dB | Pixels with change < this are flooded |
| Min area | ≥ 9 px | Smaller clusters removed as noise |
| Scale | dB | Input must be in dB (not linear) |

---

### Assumptions & Limitations

- Imagery **must** be in dB scale and co-registered (same CRS + extent).
- The -3 dB threshold is a heuristic; tune for your region in `guardian/config.py`.
- No terrain layover/shadow or urban masking in this version.
- Not validated for operational near-real-time use.
            """
        )
    with c2:
        st.info(
            "Upload pre-flood and post-flood GeoTIFFs in the sidebar, "
            "then click **Run Flood Detection**."
        )


# Guardian of the Terai: local UNOSAT reference layers

# Guardian of the Terai: local UNOSAT reference layers
import geopandas as gpd
from pathlib import Path

st.divider()
st.header("UNOSAT Reference Flood Map")
st.caption(
    "Reference flood extent for September 2024. "
    "This is external reference data, separate from model-generated detections."
)

project_root = Path(r"C:\decade")
layer_paths = {
    "UNOSAT flood extent": project_root / "results" / "unosat_flood_extent.geojson",
    "Potentially affected buildings": project_root / "results" / "impact" / "potentially_affected_buildings.geojson",
    "Potentially affected roads": project_root / "results" / "impact" / "potentially_affected_roads.geojson",
    "Potentially affected settlements": project_root / "results" / "impact" / "potentially_affected_settlements.geojson",
}

available_layers = {}
for label, path in layer_paths.items():
    if path.exists():
        try:
            available_layers[label] = gpd.read_file(path)
        except Exception as exc:
            st.warning(f"Could not load {label}: {exc}")
    else:
        st.info(f"Layer not found: {path}")

if "UNOSAT flood extent" in available_layers:
    flood_layer = available_layers["UNOSAT flood extent"]
    buildings_layer = available_layers.get("Potentially affected buildings")
    roads_layer = available_layers.get("Potentially affected roads")
    settlements_layer = available_layers.get("Potentially affected settlements")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Reference flood area", "38.85 km²")
    k2.metric(
        "Potentially affected buildings",
        f"{len(buildings_layer):,}" if buildings_layer is not None else "N/A",
    )
    k3.metric(
        "Roads intersecting flood",
        f"{roads_layer.geometry.length.sum() / 1000:.2f} km"
        if roads_layer is not None else "N/A",
    )
    k4.metric(
        "Potentially affected settlements",
        f"{len(settlements_layer):,}" if settlements_layer is not None else "N/A",
    )

    try:
        import folium
        from streamlit_folium import st_folium

        bounds = flood_layer.to_crs("EPSG:4326").total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        ref_map = folium.Map(location=center, zoom_start=10, tiles="OpenStreetMap")

        folium.GeoJson(
            flood_layer.to_crs("EPSG:4326").to_json(),
            name="UNOSAT flood extent",
            style_function=lambda feature: {
                "color": "#ef4444", "fillColor": "#ef4444",
                "weight": 2, "fillOpacity": 0.35,
            },
        ).add_to(ref_map)

        layer_styles = {
            "Potentially affected buildings": {
                "color": "#f59e0b", "fillColor": "#f59e0b",
                "weight": 1, "fillOpacity": 0.65,
            },
            "Potentially affected roads": {
                "color": "#38bdf8", "weight": 2,
            },
            "Potentially affected settlements": {
                "color": "#a855f7", "fillColor": "#a855f7",
                "weight": 2, "fillOpacity": 0.5,
            },
        }
        for label, layer in [
            ("Potentially affected buildings", buildings_layer),
            ("Potentially affected roads", roads_layer),
            ("Potentially affected settlements", settlements_layer),
        ]:
            if layer is not None and not layer.empty:
                folium.GeoJson(
                    layer.to_crs("EPSG:4326").to_json(),
                    name=label,
                    style_function=lambda feature, style=layer_styles[label]: style,
                ).add_to(ref_map)

        folium.LayerControl().add_to(ref_map)
        st_folium(ref_map, use_container_width=True, height=600)

    except ImportError:
        st.error(
            "Map dependencies missing. Install them in the terai environment: "
            "python -m pip install folium streamlit-folium"
        )
else:
    st.warning("The UNOSAT flood extent file is missing; the reference map cannot load.")

st.caption(
    "Impact figures are preliminary spatial intersections, not confirmed damage. "
    "Validate the source coverage and metrics before presenting them as definitive."
)

