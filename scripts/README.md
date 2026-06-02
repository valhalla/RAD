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
uv run python scripts/prepare_area.py \
  --area liechtenstein \
  --admins-db /path/to/admins.sqlite \
  --buffer-km 50 \
  --cache-dir /path/to/pbf-cache
```

Place the relevant Geofabrik PBFs in `--cache-dir` before running. Run without `--cache-dir`
to see which extracts intersect the buffered area (use this as a reference for which PBFs to download).

