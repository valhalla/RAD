#!/usr/bin/env bash
set -euo pipefail

# Builds Valhalla graph tiles from a PBF and bundles them into a single
# tar extract. Outputs the absolute path via GITHUB_OUTPUT.
#
# Usage: build_extract.sh <pbf_path> <tile_dir>

PBF_PATH="${1:?first argument must be the path to the OSM PBF file}"
TILE_DIR="${2:?second argument must be the tile output directory}"
CONFIG="/tmp/valhalla-build.json"

mkdir -p "$TILE_DIR"

valhalla_build_config \
  --mjolnir-tile-dir "$TILE_DIR" \
  --mjolnir-admin "$TILE_DIR/admins.sqlite" \
  --mjolnir-tile-extract "$TILE_DIR/tiles.tar" \
  > "$CONFIG"

valhalla_build_admins -c "$CONFIG" "$PBF_PATH"
valhalla_build_tiles -c "$CONFIG" "$PBF_PATH"
valhalla_build_extract -c "$CONFIG" -v

tile_count=$(find "$TILE_DIR" -name "*.gph" | wc -l)
echo "built ${tile_count} tile(s)"

test -f "$TILE_DIR/tiles.tar"
echo "tile_extract=$(realpath "$TILE_DIR/tiles.tar")" >> "$GITHUB_OUTPUT"
