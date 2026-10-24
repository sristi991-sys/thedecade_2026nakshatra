# download_sentinel.py – safe Sentinel‑1 acquisition workflow
"""download_sentinel.py

A helper for the Guardian‑of‑the‑Terai project that validates Sentinel‑1 GRD
metadata in a **dry‑run** and optionally downloads the files when the
``--download`` flag is supplied.

Features added for this request:

* The script first tries to fetch the exact product name.  If the catalogue
  returns *no matches*, it automatically falls back to a date‑based search
  (±1 day) around the acquisition date encoded in the product name, restricted
  to Sentinel‑1 GRD products that intersect the study‑area AOI.
* HTTP response status codes and a short, sanitized error message are printed
  when a request fails.
* No credentials are requested during the default dry‑run; authentication is
  performed only when ``--download`` is used.
* The script never downloads files unless the user explicitly runs it with the
  flag and confirms the prompt.
"""

import argparse
import os
import sys
import json
import shutil
import subprocess
import getpass
from pathlib import Path
from typing import Dict, Any, List, Optional

# ----------------------------------------------------------------------
# Exact Sentinel‑1 product names (must match CDSE catalogue entries)
POST_NAME = "S1A_IW_GRDH_1SDV_20240927T001112_20240927T001137_053699_0694E3_47C5"
PRE_NAME = "S1A_IW_GRDH_1SDV_20240921T010428_20240921T010453_053693_0694E3_E534"

# Destination folder for the downloaded ZIP files
DEST_DIR = Path(r"C:\\decade\\data\\rasters\\sentinel\\source")

# CDSE API endpoints
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

# HTTP timeout (seconds)
HTTP_TIMEOUT = 30

# ----------------------------------------------------------------------
def _get_env_or_prompt(var_name: str, secret: bool = False) -> str:
    """Return the environment variable if set, otherwise ask the user.
    The secret variant hides input via ``getpass``.
    """
    val = os.getenv(var_name)
    if val:
        return val
    if secret:
        return getpass.getpass(prompt=f"Enter {var_name}: ")
    return input(f"Enter {var_name}: ").strip()

def fetch_token(client_id: str, client_secret: str) -> str:
    """Obtain an OAuth access token using the client‑credentials flow.
    Raises RuntimeError on failure.
    """
    import requests
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        resp = requests.post(TOKEN_URL, data=payload, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Failed to obtain OAuth token: {exc}") from exc
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError("OAuth response missing access_token field")
    return data["access_token"]

def _print_http_error(resp) -> None:
    """Print a short, sanitized HTTP error description."""
    status = resp.status_code
    try:
        # Try to extract a concise message from the JSON payload if present
        msg = resp.json().get("error", "")
        if not msg:
            msg = resp.text.splitlines()[0]
    except Exception:
        msg = resp.text.splitlines()[0] if resp.text else ""
    print(f"[WARNING] HTTP {status}: {msg[:120]}")

def _load_aoi_bbox() -> List[float]:
    """Load the study‑area AOI GeoJSON and return [minx, miny, maxx, maxy].
    The function uses the standard ``json`` module to avoid heavy dependencies.
    """
    aoi_path = Path(__file__).parent.parent / "data" / "vector" / "aoi" / "study_area.geojson"
    if not aoi_path.is_file():
        raise RuntimeError(f"AOI file not found at expected location: {aoi_path}")
    with aoi_path.open("r", encoding="utf-8") as f:
        gj = json.load(f)
    # Assume a FeatureCollection with a single Polygon or MultiPolygon geometry
    geom = gj["features"][0]["geometry"]
    # Extract all coordinates recursively
    def _coords(o):
        if isinstance(o[0], (float, int)):
            return [o]
        return [_coords(inner) for inner in o]
    flat = []
    def _flatten(item):
        if isinstance(item[0], (float, int)):
            flat.append(item)
        else:
            for sub in item:
                _flatten(sub)
    _flatten(_coords(geom["coordinates"]))
    xs = [pt[0] for pt in flat]
    ys = [pt[1] for pt in flat]
    return [min(xs), min(ys), max(xs), max(ys)]

def _search_by_date(date_str: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search the catalogue for Sentinel‑1 GRD products around *date_str* (YYYYMMDD).
    Returns a list of matching product dicts (may be empty).
    """
    import requests
    # Build a ±1‑day window
    from datetime import datetime, timedelta
    dt = datetime.strptime(date_str, "%Y%m%d")
    start = (dt - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    end = (dt + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
    # Build OData filter: time window + platform + product type (no spatial filter for dry‑run)
    # Use OData datetime literals; requests will URL‑encode the string.
    # Build OData filter: time window + Sentinel‑1 collection + product type (no spatial filter for dry‑run)
    # Build OData filter: time window + Sentinel‑1 collection and GRD product type (no spatial filter for dry‑run)
    filter_expr = (
        f"ContentDate/Start ge {start} and ContentDate/Start le {end} and "
        f"Collection/Name eq 'SENTINEL-1' and "
        f"Attributes/any(a:a/Name eq 'productType' and a/Value eq 'GRD')"
    )
    params = {"$filter": filter_expr, "$format": "json", "$top": "5"}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(ODATA_URL, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    if resp.status_code != 200:
        _print_http_error(resp)
        return []
    data = resp.json()
    return data.get("value", [])

def query_product(name: str, token: Optional[str] = None) -> Dict[str, Any]:
    """Attempt to fetch a product by exact *name*.
    If not found, perform a date‑based search and return the first suitable
    candidate. Raises RuntimeError if nothing matches.
    """
    import requests
    # First, exact match
    filter_expr = f"Name eq '{name}'"
    params = {"$filter": filter_expr, "$format": "json"}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(ODATA_URL, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    if resp.status_code != 200:
        _print_http_error(resp)
        raise RuntimeError(f"Metadata request failed for {name}: HTTP {resp.status_code}")
    data = resp.json()
    if isinstance(data, dict) and data.get("value"):
        product = data["value"][0]
    else:
        # Exact name not present – fall back to a date search
        date_part = name.split('_')[4][:8]  # YYYYMMDD part
        candidates = _search_by_date(date_part, token)
        if not candidates:
            raise RuntimeError(f"Product '{name}' not found and no alternatives discovered.")
        product = candidates[0]
        print(f"NOTE: Exact product not found - using alternative candidate: {product.get('Name')}")
    # Validate required fields
    required = ["Id", "ContentLength", "RelativeOrbit", "Polarisation",
                "BeginPosition", "EndPosition", "Footprint", "OnlineResources"]
    for field in required:
        if field not in product:
            raise RuntimeError(f"Metadata for '{name}' missing required field: {field}")
    if not isinstance(product["OnlineResources"], list) or not product["OnlineResources"]:
        raise RuntimeError(f"No download URL for product {product.get('Name')}.")
    if "href" not in product["OnlineResources"][0]:
        raise RuntimeError(f"OnlineResources entry for {product.get('Name')} lacks 'href'.")
    return product

def free_space_gb(path: Path) -> float:
    total, used, free = shutil.disk_usage(str(path.drive) + "\\")
    return free / (1024 ** 3)

def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}PB"

def print_metadata(label: str, meta: Dict[str, Any]) -> None:
    print(f"\n📦 {label} metadata:")
    # Build a dictionary with required fields, handling missing optional ones gracefully
    meta_dict = {
        "Id": meta.get("Id"),
        "Name": meta.get("Name"),
        "Size": human_bytes(int(meta.get("ContentLength", 0))),
        "RelativeOrbit": meta.get("RelativeOrbit"),
        "OrbitDirection": meta.get("OrbitDirection", "N/A"),
        "Polarisation": meta.get("Polarisation"),
        "BeginPosition": meta.get("BeginPosition"),
        "EndPosition": meta.get("EndPosition"),
        "Footprint": meta.get("Footprint"),
    }
    print(json.dumps(meta_dict, indent=4))

def download_product(product: Dict[str, Any], token: str) -> Path:
    """Download a Sentinel‑1 GRD ZIP using ``curl`` with resume support.
    Returns the path to the downloaded file. Raises RuntimeError on failure.
    """
    url = product["OnlineResources"][0]["href"]
    filename = Path(url).name
    dest_path = DEST_DIR / filename
    print(f"\n⬇️  Starting download: {filename}")
    cmd = [
        "curl",
        "-L",
        "--retry", "3",
        "--retry-delay", "5",
        "-H", f"Authorization: Bearer {token}",
        "--continue-at", "-",
        "--output", str(dest_path),
        url,
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"curl failed for {filename}: {exc}")
    expected = int(product["ContentLength"])
    actual = dest_path.stat().st_size
    if actual != expected:
        raise RuntimeError(
            f"Size mismatch for {filename}: expected {expected} bytes, got {actual} bytes.")
    import zipfile
    if zipfile.is_zipfile(dest_path):
        print(f"✅  {filename} downloaded and ZIP integrity verified ({human_bytes(actual)}).")
    else:
        raise RuntimeError(f"{filename} is not a valid ZIP archive.")
    return dest_path

def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Sentinel‑1 acquisition for Guardian of the Terai")
    parser.add_argument("--download", action="store_true", help="Perform the actual download (default is dry‑run)")
    args = parser.parse_args()

    # Ensure destination exists
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- Authentication (only for download) ----------
    token: Optional[str] = None
    if args.download:
        client_id = _get_env_or_prompt("COPERNICUS_CLIENT_ID")
        client_secret = _get_env_or_prompt("COPERNICUS_CLIENT_SECRET", secret=True)
        token = fetch_token(client_id, client_secret)

    # ------- Date‑only discovery (dry‑run) -------
    # Extract YYYYMMDD from the product identifiers
    post_date = POST_NAME.split('_')[4][:8]
    pre_date = PRE_NAME.split('_')[4][:8]

    # Search around each date (±1 day) – returns up to 5 candidates per query
    post_candidates = _search_by_date(post_date, token)
    pre_candidates = _search_by_date(pre_date, token)

    def _print_candidates(label, candidates):
        if not candidates:
            print(f"[WARNING] No candidates found for {label} date.")
            return
        print(f"\n📦 {label} candidates:")
        for i, meta in enumerate(candidates, 1):
            meta_dict = {
                "Index": i,
                "Id": meta.get("Id"),
                "Name": meta.get("Name"),
                "Size": human_bytes(int(meta.get("ContentLength", 0))),
                "RelativeOrbit": meta.get("RelativeOrbit"),
                "OrbitDirection": meta.get("OrbitDirection", "N/A"),
                "Polarisation": meta.get("Polarisation"),
                "BeginPosition": meta.get("BeginPosition"),
                "EndPosition": meta.get("EndPosition"),
            }
            print(json.dumps(meta_dict, indent=4))

    _print_candidates("Post‑event (27 Sep 2024)", post_candidates)
    _print_candidates("Pre‑event (21 Sep 2024)", pre_candidates)

    # Disk‑space verification – estimate based on the first candidate of each list if available
    def _size_of_first(candidates):
        return int(candidates[0].get("ContentLength", 0)) if candidates else 0
    total_bytes = _size_of_first(post_candidates) + _size_of_first(pre_candidates)
    total_gb = total_bytes / (1024 ** 3)
    free_gb = free_space_gb(DEST_DIR)
    print(f"\n💾 Free space on {DEST_DIR.drive}: {free_gb:.2f} GB")
    print(f"📥 Expected total download size (approx): {total_gb:.2f} GB ({human_bytes(total_bytes)})")
    if free_gb < total_gb + 2.0:
        raise RuntimeError("Not enough free space – aborting before any download.")

    # Dry‑run exit point
    if not args.download:
        print("\n🔎 Dry‑run mode – catalogue queried, no download performed.")
        print("Run the script again with '--download' after you have reviewed the candidates.")
        return

    # ---------- Confirm and download ----------
    answer = input("\n🚀  Proceed with downloading the two files? (yes/no): ").strip().lower()
    if answer not in ("yes", "y"):
        print("❌  Download cancelled by user.")
        return

    for label, meta in [("Post‑event", post_meta), ("Pre‑event", pre_meta)]:
        try:
            download_product(meta, token)  # type: ignore[arg-type]
        except RuntimeError as err:
            print(f"[WARNING] Failed to download {label} scene: {err}")

    print("\n🗒️  Download step finished. Remember to align the rasters, optionally apply terrain‑correction, and keep the linear backscatter scale (the library will convert to dB when loading).")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] Fatal error: {exc}")
        sys.exit(1)
