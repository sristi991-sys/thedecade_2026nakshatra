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
