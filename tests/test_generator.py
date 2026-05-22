"""Tests for route_generator.generator."""

from __future__ import annotations

import json
import random

from shapely.geometry import Point

from route_generator.generator import (
    COSTING_BUNDLES,
    build_requests,
    load_switzerland_polygon,
    sample_point_in_polygon,
    write_jsonl,
)

# ---------------------------------------------------------------------------
# Polygon loading
# ---------------------------------------------------------------------------


def test_load_switzerland_polygon_returns_valid_geometry():
    polygon = load_switzerland_polygon()
    assert polygon is not None
    assert not polygon.is_empty
    assert polygon.is_valid


def test_switzerland_polygon_bounds():
    """Bounding box should match the known extent of Switzerland."""
    polygon = load_switzerland_polygon()
    minx, miny, maxx, maxy = polygon.bounds
    # Rough Switzerland extents — if these fail the GeoJSON is wrong
    assert 5.9 < minx < 6.1, f"Unexpected western bound: {minx}"
    assert 45.7 < miny < 45.9, f"Unexpected southern bound: {miny}"
    assert 10.4 < maxx < 10.5, f"Unexpected eastern bound: {maxx}"
    assert 47.8 < maxy < 47.9, f"Unexpected northern bound: {maxy}"


def test_known_point_inside_switzerland():
    """Zurich city center should be inside the polygon."""
    polygon = load_switzerland_polygon()
    zurich = Point(8.5417, 47.3769)
    assert zurich.within(polygon)


def test_known_point_outside_switzerland():
    """Paris should not be inside the polygon."""
    polygon = load_switzerland_polygon()
    paris = Point(2.3522, 48.8566)
    assert not paris.within(polygon)


# ---------------------------------------------------------------------------
# Coordinate sampling
# ---------------------------------------------------------------------------


def test_sample_point_in_polygon_is_within():
    polygon = load_switzerland_polygon()
    rng = random.Random(42)
    for _ in range(50):
        lon, lat = sample_point_in_polygon(polygon, rng)
        assert Point(lon, lat).within(polygon), f"Point ({lon}, {lat}) outside polygon"


def test_sample_point_precision():
    """Coordinates should be rounded to 6 decimal places."""
    polygon = load_switzerland_polygon()
    rng = random.Random(0)
    lon, lat = sample_point_in_polygon(polygon, rng)
    assert lon == round(lon, 6)
    assert lat == round(lat, 6)


def test_sample_point_reproducible_with_seed():
    polygon = load_switzerland_polygon()
    rng1 = random.Random(99)
    rng2 = random.Random(99)
    assert sample_point_in_polygon(polygon, rng1) == sample_point_in_polygon(polygon, rng2)


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------


def test_build_requests_count():
    polygon = load_switzerland_polygon()
    rng = random.Random(1)
    reqs = list(build_requests(n_pairs=10, polygon=polygon, rng=rng))
    assert len(reqs) == 10 * len(COSTING_BUNDLES)


def test_build_requests_structure():
    """Each request must have locations, costing, and costing_options."""
    polygon = load_switzerland_polygon()
    rng = random.Random(2)
    reqs = list(build_requests(n_pairs=3, polygon=polygon, rng=rng))
    for req in reqs:
        assert "locations" in req
        assert len(req["locations"]) == 2
        assert "lon" in req["locations"][0]
        assert "lat" in req["locations"][0]
        assert "costing" in req
        assert "costing_options" in req


def test_build_requests_coordinates_in_switzerland():
    """All generated coordinates should be within Switzerland."""
    polygon = load_switzerland_polygon()
    rng = random.Random(3)
    reqs = list(build_requests(n_pairs=20, polygon=polygon, rng=rng))
    for req in reqs:
        for loc in req["locations"]:
            assert Point(loc["lon"], loc["lat"]).within(polygon)


def test_build_requests_custom_bundles():
    polygon = load_switzerland_polygon()
    rng = random.Random(4)
    bundles = [{"costing": "auto", "costing_options": {}}]
    reqs = list(build_requests(n_pairs=5, polygon=polygon, rng=rng, costing_bundles=bundles))
    assert len(reqs) == 5
    assert all(r["costing"] == "auto" for r in reqs)


def test_build_requests_reproducible_with_seed():
    polygon = load_switzerland_polygon()
    reqs1 = list(build_requests(n_pairs=10, polygon=polygon, rng=random.Random(42)))
    reqs2 = list(build_requests(n_pairs=10, polygon=polygon, rng=random.Random(42)))
    assert reqs1 == reqs2


# ---------------------------------------------------------------------------
# JSONL output
# ---------------------------------------------------------------------------


def test_write_jsonl_line_count(tmp_path):
    polygon = load_switzerland_polygon()
    rng = random.Random(5)
    reqs = build_requests(n_pairs=10, polygon=polygon, rng=rng)
    out = tmp_path / "test.jsonl"
    n = write_jsonl(reqs, out)
    lines = out.read_text().strip().split("\n")
    assert n == len(lines) == 10 * len(COSTING_BUNDLES)


def test_write_jsonl_valid_json(tmp_path):
    polygon = load_switzerland_polygon()
    rng = random.Random(6)
    reqs = build_requests(n_pairs=5, polygon=polygon, rng=rng)
    out = tmp_path / "test.jsonl"
    write_jsonl(reqs, out)
    for line in out.read_text().strip().split("\n"):
        obj = json.loads(line)  # must not raise
        assert "locations" in obj
        assert "costing" in obj


def test_write_jsonl_no_trailing_newline_issues(tmp_path):
    """Each line ends with exactly one newline."""
    polygon = load_switzerland_polygon()
    rng = random.Random(7)
    reqs = build_requests(n_pairs=2, polygon=polygon, rng=rng)
    out = tmp_path / "test.jsonl"
    write_jsonl(reqs, out)
    content = out.read_text()
    lines = content.split("\n")
    # Last element after split on a file ending in \n is always ""
    assert lines[-1] == ""
