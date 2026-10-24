from pathlib import Path
import geopandas as gpd

root = Path(r"C:\decade")
flood_path = root / "results" / "unosat_flood_extent.geojson"
buildings_path = root / "data" / "vector" / "osm" / "buildings.geojson"
roads_path = root / "data" / "vector" / "osm" / "roads.geojson"
settlements_path = root / "data" / "vector" / "osm" / "settlements.geojson"
outdir = root / "results" / "impact"
outdir.mkdir(parents=True, exist_ok=True)

print("Loading flood layer...")
flood = gpd.read_file(flood_path)
if flood.crs is None:
    raise ValueError("Flood layer has no CRS.")

# UTM zone 45N is appropriate for this Nepal study area.
crs = "EPSG:32645"
flood = flood.to_crs(crs)
flood = flood[flood.geometry.notna() & ~flood.geometry.is_empty]
flood_union = flood.geometry.union_all()

print(f"Flood polygons: {len(flood)}")
print(f"Flood area: {flood_union.area / 1_000_000:.2f} km²")

if buildings_path.exists():
    print("\nLoading buildings (this may take a while)...")
    buildings = gpd.read_file(buildings_path)
    print("Total building features:", len(buildings))
    buildings = buildings.to_crs(crs)
    buildings = buildings[
        buildings.geometry.notna() & ~buildings.geometry.is_empty
    ]
    affected = buildings[buildings.geometry.intersects(flood_union)]
    print("Potentially affected buildings:", len(affected))
    affected.to_crs("EPSG:4326").to_file(
        outdir / "potentially_affected_buildings.geojson",
        driver="GeoJSON"
    )
else:
    print("Buildings file not found:", buildings_path)

if roads_path.exists():
    print("\nLoading roads...")
    roads = gpd.read_file(roads_path)
    print("Total road features:", len(roads))
    roads = roads.to_crs(crs)
    roads = roads[
        roads.geometry.notna() & ~roads.geometry.is_empty
    ]
    road_intersections = roads.geometry.intersection(flood_union)
    road_length_km = road_intersections.length.sum() / 1000
    print(f"Road length inside flood extent: {road_length_km:.2f} km")
    roads.loc[road_intersections.length > 0].to_crs("EPSG:4326").to_file(
        outdir / "potentially_affected_roads.geojson",
        driver="GeoJSON"
    )
else:
    print("Roads file not found:", roads_path)

if settlements_path.exists():
    print("\nLoading settlements...")
    settlements = gpd.read_file(settlements_path)
    print("Total settlement features:", len(settlements))
    settlements = settlements.to_crs(crs)
    settlements = settlements[
        settlements.geometry.notna() & ~settlements.geometry.is_empty
    ]
    affected_settlements = settlements[
        settlements.geometry.intersects(flood_union)
    ]
    print("Potentially affected settlements:", len(affected_settlements))
    affected_settlements.to_crs("EPSG:4326").to_file(
        outdir / "potentially_affected_settlements.geojson",
        driver="GeoJSON"
    )
else:
    print("Settlements file not found:", settlements_path)

print("\nAnalysis finished. Outputs:", outdir)
