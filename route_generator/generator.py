"""
Route request generator for Valhalla RAD.

Generates randomized Valhalla /route requests as JSONL, using random
coordinate pairs within the Switzerland country polygon.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from pathlib import Path

from shapely.geometry import Point, shape

# ---------------------------------------------------------------------------
# Costing bundles
# ---------------------------------------------------------------------------
# Each bundle is one complete set of costing parameters. For each coordinate
# pair we generate, we emit one request per bundle - so total lines in the
# output is n_pairs * len(COSTING_BUNDLES).
#
# These are intentionally minimal and hardcoded for now. Once the Valhalla
# OpenAPI spec lands, we'll replace/extend this with
# spec-driven randomized costing options.
COSTING_BUNDLES: list[dict] = [
    {"costing": "auto", "costing_options": {"auto": {"use_highways": 1.0}}},
]


# ---------------------------------------------------------------------------
# Polygon loading
# ---------------------------------------------------------------------------


def load_switzerland_polygon():
    """Load the Switzerland country polygon from the vendored GeoJSON file.

    Returns a shapely geometry object. The file lives in data/switzerland.geojson
    relative to this package and is checked into the repo — no network call needed.
    """
    data_path = Path(__file__).parent.parent / "data" / "switzerland.geojson"
    with data_path.open() as f:
        geojson = json.load(f)
    # FeatureCollection with one feature (the country polygon)
    return shape(geojson["features"][0]["geometry"])


# ---------------------------------------------------------------------------
# Coordinate sampling
# ---------------------------------------------------------------------------


def sample_point_in_polygon(polygon, rng: random.Random) -> tuple[float, float]:
    """Sample a random (lon, lat) point that lies within the given polygon.

    Uses rejection sampling against the polygon bounding box. For Switzerland
    the bounding box hit rate is ~59.5%, so on average 1.68 attempts per valid
    point — fast enough that we never need to worry about performance here.

    Returns:
        (lon, lat) tuple, both rounded to 6 decimal places (~0.1m precision).
    """
    minx, miny, maxx, maxy = polygon.bounds
    while True:
        lon = rng.uniform(minx, maxx)
        lat = rng.uniform(miny, maxy)
        if Point(lon, lat).within(polygon):
            return round(lon, 6), round(lat, 6)


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------


def build_requests(
    n_pairs: int,
    polygon,
    rng: random.Random,
    costing_bundles: list[dict] | None = None,
) -> Iterator[dict]:
    """Yield Valhalla /route request dicts.

    For each of n_pairs random coordinate pairs, yields one request per
    costing bundle. Total output: n_pairs * len(costing_bundles) requests.

    Args:
        n_pairs: Number of origin/destination coordinate pairs to generate.
        polygon: Shapely polygon to sample coordinates from.
        rng: Random instance (seeded or not) — caller controls reproducibility.
        costing_bundles: List of costing dicts. Defaults to COSTING_BUNDLES.

    Yields:
        dict: A complete Valhalla /route request body, ready to serialize as JSON.
    """
    if costing_bundles is None:
        costing_bundles = COSTING_BUNDLES

    for _ in range(n_pairs):
        origin_lon, origin_lat = sample_point_in_polygon(polygon, rng)
        dest_lon, dest_lat = sample_point_in_polygon(polygon, rng)

        for bundle in costing_bundles:
            yield {
                "locations": [
                    {"lon": origin_lon, "lat": origin_lat},
                    {"lon": dest_lon, "lat": dest_lat},
                ],
                **bundle,
            }


# ---------------------------------------------------------------------------
# JSONL output
# ---------------------------------------------------------------------------


def write_jsonl(requests: Iterator[dict], output_path: Path) -> int:
    """Write request dicts to a JSONL file, one JSON object per line.

    Args:
        requests: Iterator of request dicts from build_requests().
        output_path: Path to write the JSONL file to.

    Returns:
        Total number of lines written.
    """
    count = 0
    with output_path.open("w") as f:
        for req in requests:
            f.write(json.dumps(req, separators=(",", ":")) + "\n")
            count += 1
    return count
