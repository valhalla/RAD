"""
Prepare OSM extract for a given country area.

Queries admins.sqlite for the exact country polygon, buffers it by the requested
distance, then cuts and merges the relevant Geofabrik PBFs into a single .osm.pbf

"""

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.wkt import loads as wkt_loads


def load_polygon_from_admins(admins_db: Path, area: str) -> BaseGeometry:
    """Load the exact country polygon from admins.sqlite at admin level 2.

    Closes the connection before handing off to Shapely to avoid a GEOS
    version conflict with mod_spatialite.

    :param admins_db: Path to admins.sqlite.
    :param area: Country name (case-insensitive).
    :returns: Shapely geometry of the country polygon.
    :raises SystemExit: If the area is not found.
    """
    conn = sqlite3.connect(admins_db)
    conn.enable_load_extension(True)
    conn.load_extension("mod_spatialite")
    row = conn.execute(
        "SELECT ST_AsText(geom) FROM admins WHERE admin_level = 2 AND lower(name) = lower(?)",
        (area,),
    ).fetchone()
    conn.close()

    if row is None:
        sys.exit(f"Area '{area}' not found in {admins_db} at admin_level=2.")
    return wkt_loads(row[0])


def buffer_polygon(polygon: BaseGeometry, buffer_km: float) -> BaseGeometry:
    """Buffer a WGS84 polygon by an approximate degree equivalent of the given distance.

    Uses a simple degree approximation (1° ≈ 111 km) rather than a metric projection.
    Sufficient for the graph build buffer use case.

    :param polygon: Shapely geometry in WGS84 (EPSG:4326).
    :param buffer_km: Buffer distance in kilometres.
    :returns: Buffered Shapely geometry in WGS84.
    """
    return polygon.buffer(buffer_km / 111.0)


def save_geojson(polygon: BaseGeometry, path: Path) -> None:
    """Write a Shapely geometry to a GeoJSON FeatureCollection file.

    :param polygon: Shapely geometry to serialize.
    :param path: Destination path.
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(polygon), "properties": {}}],
    }
    path.write_text(json.dumps(geojson))


def collect_pbfs(pbf_dir: Path) -> list[Path]:
    """Collect all .osm.pbf files from a directory.

    :param pbf_dir: Directory containing manually downloaded PBF files.
    :returns: Sorted list of PBF paths found.
    :raises SystemExit: If the directory is missing or empty.
    """
    if not pbf_dir.exists():
        sys.exit(f"--pbf-dir '{pbf_dir}' does not exist.")
    paths = sorted(pbf_dir.glob("*.osm.pbf"))
    if not paths:
        sys.exit(f"No .osm.pbf files found in '{pbf_dir}'.")
    return paths


def build_extract(pbf_paths: list[Path], polygon_path: Path, output_path: Path) -> None:
    """Cut each PBF to the buffered polygon, then merge the cuts.

    :param pbf_paths: List of input PBF files.
    :param polygon_path: Path to the buffered polygon GeoJSON.
    :param output_path: Path for the output .osm.pbf.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        cut_paths = []
        for pbf in pbf_paths:
            cut = tmp / f"{pbf.stem}_cut.osm.pbf"
            print(f"Extracting {pbf.name}...")
            subprocess.run(
                [
                    "osmium",
                    "extract",
                    "--polygon",
                    str(polygon_path),
                    str(pbf),
                    "-o",
                    str(cut),
                    "--overwrite",
                ],
                check=True,
            )
            cut_paths.append(cut)

        print("Merging extracts...")
        subprocess.run(
            ["osmium", "merge", *[str(p) for p in cut_paths], "-o", str(output_path), "--overwrite"],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare OSM extract for a Valhalla graph build.")
    parser.add_argument(
        "--area",
        required=True,
        help="Country name in admins.sqlite (case-insensitive, e.g. 'liechtenstein')",
    )
    parser.add_argument("--admins-db", required=True, type=Path, help="Path to admins.sqlite")
    parser.add_argument(
        "--buffer-km", type=float, default=50.0, help="Buffer distance in km (default: 50)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .osm.pbf path (default: data/{area}_graph.osm.pbf)",
    )
    parser.add_argument(
        "--pbf-dir",
        required=True,
        type=Path,
        help="Directory of manually downloaded Geofabrik PBFs",
    )
    args = parser.parse_args()

    area_slug = args.area.lower().replace(" ", "_")
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    output_path = args.output or data_dir / f"{area_slug}_graph.osm.pbf"

    print(f"Loading polygon for '{args.area}'...")
    polygon = load_polygon_from_admins(args.admins_db, args.area)
    save_geojson(polygon, data_dir / f"{area_slug}.geojson")
    print(f"Exact polygon → {data_dir / f'{area_slug}.geojson'}")

    print(f"Buffering by {args.buffer_km} km...")
    buffered = buffer_polygon(polygon, args.buffer_km)
    buffered_path = data_dir / f"{area_slug}_buffered.geojson"
    save_geojson(buffered, buffered_path)
    print(f"Buffered polygon → {buffered_path}")

    pbf_paths = collect_pbfs(args.pbf_dir)
    print(f"Using {len(pbf_paths)} PBF(s) from {args.pbf_dir}:")
    for p in pbf_paths:
        print(f"  {p.name}")

    build_extract(pbf_paths, buffered_path, output_path)
    print(f"Done → {output_path}")


if __name__ == "__main__":
    main()
