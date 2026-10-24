from pathlib import Path
import geopandas as gpd

root = Path(r"C:\decade")
ref = root / "data" / "vector" / "reference" / "FL20240928NPL_SHP"
aoi_path = root / "data" / "vector" / "aoi" / "study_area.geojson"
out_path = root / "results" / "unosat_flood_extent.geojson"

try:
    flood_files = list(ref.glob("*FloodExtent*.shp"))
    if not flood_files:
        raise FileNotFoundError(f"No FloodExtent shapefile found in {ref}")

    flood_path = flood_files[0]
    print("Flood file:", flood_path)

    flood = gpd.read_file(flood_path)
    aoi = gpd.read_file(aoi_path)

    print("\nFlood CRS:", flood.crs)
    print("Flood features:", len(flood))
    print("Flood bounds:", flood.total_bounds)
    print("Flood geometry types:", flood.geom_type.value_counts().to_dict())
    print("Study area CRS:", aoi.crs)
    print("Study area bounds:", aoi.total_bounds)

    if flood.crs is None or aoi.crs is None:
        raise ValueError("A dataset has no CRS; do not guess its coordinates.")

    flood = flood.to_crs("EPSG:4326")
    aoi = aoi.to_crs("EPSG:4326")
    clipped = gpd.clip(flood, aoi)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    clipped.to_file(out_path, driver="GeoJSON")

    area_km2 = clipped.to_crs("EPSG:32645").geometry.area.sum() / 1_000_000

    print("\nSUCCESS")
    print("Output:", out_path)
    print("Output exists:", out_path.exists())
    print("Clipped features:", len(clipped))
    print(f"Clipped area: {area_km2:.4f} km²")
except Exception as e:
    print("\nERROR:", type(e).__name__, str(e))
    raise
