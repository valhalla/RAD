"""
Prepare OSM extract for a given country area.

Queries admins.sqlite for the exact country polygon, buffers it by the requested
distance, then downloads, merges, and extracts the relevant Geofabrik PBFs into a
single .osm.pbf ready for valhalla_build_tiles.

System dependencies: libsqlite3-mod-spatialite, osmium-tool
See scripts/README.md for install instructions.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform
from shapely.wkt import loads as wkt_loads

GEOFABRIK_INDEX_URL = "https://download.geofabrik.de/index-v1.json"


def load_polygon_from_admins(admins_db: Path, area: str) -> object:
    """Load the exact country polygon from admins.sqlite at admin level 2.

    Uses mod_spatialite to read SpatiaLite geometry blobs via ST_AsText,
    then closes the connection before handing off to Shapely to avoid a
    GEOS version conflict between the two libraries.

    :param admins_db: Path to admins.sqlite.
    :param area: Country name as stored in the admins table (case-sensitive).
    :returns: Shapely geometry of the country polygon.
    :raises SystemExit: If the area is not found in the database.
    """
    conn = sqlite3.connect(admins_db)
    conn.enable_load_extension(True)
    conn.load_extension("mod_spatialite")

    row = conn.execute(
        "SELECT ST_AsText(geom) FROM admins WHERE admin_level = 2 AND name = ?",
        (area,),
    ).fetchone()
    conn.close()

    if row is None:
        sys.exit(f"Area '{area}' not found in {admins_db} at admin_level=2.")

    return wkt_loads(row[0])


def buffer_polygon(polygon: object, buffer_km: float) -> object:
    """Buffer a WGS84 polygon by the given distance in kilometres.

    Projects to UTM (zone auto-detected from polygon centroid), buffers in
    metres, then reprojects back to WGS84.

    :param polygon: Shapely geometry in WGS84 (EPSG:4326).
    :param buffer_km: Buffer distance in kilometres.
    :returns: Buffered Shapely geometry in WGS84.
    """
    centroid = polygon.centroid
    utm_crs = f"+proj=utm +zone={int((centroid.x + 180) / 6) + 1} +datum=WGS84"

    to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True).transform
    to_wgs84 = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True).transform

    return transform(to_wgs84, transform(to_utm, polygon).buffer(buffer_km * 1000))


def save_geojson(polygon: object, path: Path) -> None:
    """Write a Shapely geometry to a GeoJSON file as a single Feature.

    :param polygon: Shapely geometry to serialize.
    :param path: Destination path.
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(polygon), "properties": {}}],
    }
    path.write_text(json.dumps(geojson))


def find_intersecting_urls(buffered_polygon: object) -> list[str]:
    """Find Geofabrik PBF URLs whose geometries intersect the buffered polygon.

    Results include all intersecting extracts at every hierarchy level — use this
    as a reference to decide which PBFs to download manually into your cache dir.

    :param buffered_polygon: Shapely geometry of the buffered area in WGS84.
    :returns: List of intersecting PBF download URLs.
    :raises SystemExit: If the Geofabrik index cannot be fetched.
    """
    resp = requests.get(GEOFABRIK_INDEX_URL, timeout=30)
    if not resp.ok:
        sys.exit(f"Failed to fetch Geofabrik index: {resp.status_code}")

    urls = []
    for feature in resp.json()["features"]:
        if shape(feature["geometry"]).intersects(buffered_polygon):
            urls.append(feature["properties"]["urls"]["pbf"])
    return urls


def download_pbfs(urls: list[str], dest_dir: Path) -> list[Path]:
    """Download PBF files to dest_dir, skipping already-downloaded files.

    :param urls: List of Geofabrik PBF URLs.
    :param dest_dir: Directory to store downloaded files.
    :returns: List of paths to downloaded PBF files.
    """
    paths = []
    for url in urls:
        dest = dest_dir / Path(url).name
        if not dest.exists():
            print(f"Downloading {url}")
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with dest.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        else:
            print(f"Already downloaded: {dest.name}")
        paths.append(dest)
    return paths


def collect_pbfs_from_cache(cache_dir: Path) -> list[Path]:
    """Collect all .osm.pbf files from a cache directory.

    :param cache_dir: Directory containing manually downloaded PBF files.
    :returns: List of PBF paths found.
    :raises SystemExit: If the cache dir is empty or doesn't exist.
    """
    if not cache_dir.exists():
        sys.exit(f"Cache dir '{cache_dir}' does not exist. Create it and place your PBF files there.")

    paths = sorted(cache_dir.glob("*.osm.pbf"))
    if not paths:
        sys.exit(f"No .osm.pbf files found in '{cache_dir}'. Download the relevant PBFs there first.")

    return paths


def build_extract(pbf_paths: list[Path], polygon_path: Path, output_path: Path) -> None:
    """Merge PBFs and extract to the buffered polygon using osmium.

    :param pbf_paths: List of input PBF files.
    :param polygon_path: Path to the buffered polygon GeoJSON.
    :param output_path: Path for the output .osm.pbf.
    """
    with tempfile.NamedTemporaryFile(suffix=".osm.pbf", delete=False) as tmp:
        merged_path = Path(tmp.name)

    try:
        print("Merging PBFs...")
        subprocess.run(
            ["osmium", "merge", *[str(p) for p in pbf_paths], "-o", str(merged_path), "--overwrite"],
            check=True,
        )

        print("Extracting to buffered polygon...")
        subprocess.run(
            [
                "osmium",
                "extract",
                "--polygon",
                str(polygon_path),
                str(merged_path),
                "-o",
                str(output_path),
                "--overwrite",
            ],
            check=True,
        )
    finally:
        merged_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare OSM extract for a Valhalla graph build.")
    parser.add_argument(
        "--area",
        required=True,
        help="Country name exactly as stored in admins.sqlite, case-sensitive (e.g. 'Liechtenstein')",
    )
    parser.add_argument("--admins-db", required=True, type=Path, help="Path to admins.sqlite")
    parser.add_argument(
        "--buffer-km", type=float, default=50.0, help="Buffer distance in km (default: 50)"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Output .osm.pbf path (default: {area}_graph.osm.pbf)"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Directory of manually downloaded PBFs; skips all downloading and uses these directly",
    )
    args = parser.parse_args()

    area_slug = args.area.lower().replace(" ", "_")
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    output_path = args.output or Path(f"{area_slug}_graph.osm.pbf")

    print(f"Loading polygon for '{args.area}' from {args.admins_db}...")
    polygon = load_polygon_from_admins(args.admins_db, args.area)

    exact_path = data_dir / f"{area_slug}.geojson"
    save_geojson(polygon, exact_path)
    print(f"Exact polygon → {exact_path}")

    print(f"Buffering by {args.buffer_km} km...")
    buffered = buffer_polygon(polygon, args.buffer_km)

    buffered_path = data_dir / f"{area_slug}_buffered.geojson"
    save_geojson(buffered, buffered_path)
    print(f"Buffered polygon → {buffered_path}")

    if args.cache_dir:
        print(f"Using PBFs from cache dir: {args.cache_dir}")
        pbf_paths = collect_pbfs_from_cache(args.cache_dir)
        print(f"Found {len(pbf_paths)} PBF(s):")
        for p in pbf_paths:
            print(f"  {p.name}")
        build_extract(pbf_paths, buffered_path, output_path)
    else:
        print("Fetching Geofabrik index to find intersecting extracts...")
        urls = find_intersecting_urls(buffered)
        print(f"\nIntersecting extracts ({len(urls)}):")
        for u in urls:
            print(f"  {u}")
        print(
            "\nWARNING: some of these extracts are very large (several GB)."
            " Consider downloading only the ones you need manually into a"
            " --cache-dir instead."
        )
        answer = input("\nProceed with downloading all of the above? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted. Download the PBFs you need into a directory and re-run with --cache-dir.")
            sys.exit(0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            pbf_paths = download_pbfs(urls, Path(tmp_dir))
            build_extract(pbf_paths, buffered_path, output_path)

    print(f"Done → {output_path}")


if __name__ == "__main__":
    main()
