"""
Route request generator for Valhalla RAD.

Generates randomized Valhalla /route requests as JSONL, using random
coordinate pairs within the Switzerland country polygon.
"""

import json
import random
from collections.abc import Iterator
from pathlib import Path

from shapely.geometry import Point, Polygon, shape

# temp until costing options are randomized via OpenAPI spec
COSTING_BUNDLES: list[dict] = [
    {"costing": "auto", "costing_options": {"auto": {"use_highways": 1.0}}},
]


def load_switzerland_polygon() -> Polygon:
    """Load the Switzerland country polygon from the vendored GeoJSON file.

    :returns: Shapely geometry of the Switzerland country polygon.
    """
    data_path = Path(__file__).parent.parent / "data" / "switzerland.geojson"
    with data_path.open() as f:
        geojson = json.load(f)
    return shape(geojson["features"][0]["geometry"])


def sample_point_in_polygon(polygon: Polygon, rng: random.Random) -> tuple[float, float]:
    """Sample a random (lon, lat) point within the polygon using rejection sampling.

    :param polygon: Shapely polygon to sample from.
    :param rng: Random instance — caller controls reproducibility.
    :returns: (lon, lat) tuple rounded to 6 decimal places (~0.1m precision).
    """
    minx, miny, maxx, maxy = polygon.bounds
    while True:
        lon = rng.uniform(minx, maxx)
        lat = rng.uniform(miny, maxy)
        if Point(lon, lat).within(polygon):
            return round(lon, 6), round(lat, 6)


def build_requests(
    n_pairs: int,
    polygon: Polygon,
    rng: random.Random,
    costing_bundles: list[dict] | None = None,
) -> Iterator[dict]:
    """Yield Valhalla /route request dicts.

    :param n_pairs: Number of origin/destination coordinate pairs to generate.
    :param polygon: Shapely polygon to sample coordinates from.
    :param rng: Random instance — caller controls reproducibility.
    :param costing_bundles: List of costing dicts. Defaults to COSTING_BUNDLES.
    :returns: Complete Valhalla /route request body per pair per bundle.
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


def write_jsonl(requests: Iterator[dict], output_path: Path) -> int:
    """Write request dicts to a JSONL file, one JSON object per line.

    :param requests: Iterator of request dicts from build_requests().
    :param output_path: Path to write the JSONL file to.
    :returns: Total number of lines written.
    """
    count = 0
    with output_path.open("w") as f:
        for req in requests:
            f.write(json.dumps(req, separators=(",", ":")) + "\n")
            count += 1
    return count
