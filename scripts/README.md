# scripts/

## prepare_area.py

Prepares an OSM extract for a given country, ready for `valhalla_build_tiles`.

**What it does:**
1. Queries `admins.sqlite` for the exact country polygon at admin level 2
2. Saves it to `data/{area}.geojson` (OSM-sourced)
3. Buffers by `--buffer-km` to avoid graph edge effects, saves `data/{area}_buffered.geojson`
4. Cuts each PBF to the buffered polygon, then merges the cuts into a single `.osm.pbf`

### System dependencies

```bash
sudo apt-get install -y libsqlite3-mod-spatialite osmium-tool
```

### Usage

```bash
uv run python scripts/prepare_area.py --help
```

Download the relevant Geofabrik PBFs manually into a directory and pass it via `--pbf-dir`.
For Liechtenstein, the required extracts are `liechtenstein-latest`, `switzerland-latest`, and `austria-latest`.

**Notes**

**Extract before merge.** Cutting each PBF to the buffered polygon first keeps the merge small and avoids osmium failing on overlapping border objects across files with different timestamps.
