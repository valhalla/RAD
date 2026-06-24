# RAD — Routing Regression Pipeline

```mermaid
flowchart TD
    TRIGGER(["`**workflow_dispatch**
    valhalla_ref_old · valhalla_ref_new`"])

    TRIGGER -->|matrix: label=old| OLD_JOB
    TRIGGER -->|matrix: label=new| NEW_JOB

    subgraph OLD_JOB ["old ref runner (ubuntu-latest)"]
        direction TB
        O1["① build-valhalla
        composite action
        ─────────────────
        checkout valhalla at old ref
        install-linux-deps.sh
        restore ccache ← actions/cache
        pip wheel . -Cbuild-dir=/tmp/valhalla-build
        save ccache → actions/cache
        pip install wheel"]

        O2["② build-tiles
        composite action
        ─────────────────
        valhalla_build_config
        valhalla_build_admins
        valhalla_build_tiles
        valhalla_build_extract → tiles.tar"]

        O3["③ run routes
        ─────────────────
        run_routes.py
        pyvalhalla Actor in-process
        → responses-old.jsonl"]

        O4[/"④ upload artifact
        responses-old.jsonl"/]

        O1 --> O2 --> O3 --> O4
    end

    subgraph NEW_JOB ["new ref runner (ubuntu-latest)"]
        direction TB
        N1["① build-valhalla
        composite action
        ─────────────────
        checkout valhalla at new ref
        install-linux-deps.sh
        restore ccache ← actions/cache
        pip wheel . -Cbuild-dir=/tmp/valhalla-build
        save ccache → actions/cache
        pip install wheel"]

        N2["② build-tiles
        composite action
        ─────────────────
        valhalla_build_config
        valhalla_build_admins
        valhalla_build_tiles
        valhalla_build_extract → tiles.tar"]

        N3["③ run routes
        ─────────────────
        run_routes.py
        pyvalhalla Actor in-process
        → responses-new.jsonl"]

        N4[/"④ upload artifact
        responses-new.jsonl"/]

        N1 --> N2 --> N3 --> N4
    end

    O4 --> DIFF
    N4 --> DIFF

    subgraph DIFF ["diff-and-store (needs: regression)"]
        direction TB
        D1["download both artifacts
        ─────────────────
        responses-old.jsonl
        responses-new.jsonl"]

        D2["diff_responses.py
        ─────────────────
        geometry delta · duration delta
        instruction diff · severity score"]

        D3["git commit → valhalla/RAD-data
        ─────────────────
        diffs/{run_id}.json
        push via RAD_DATA_TOKEN"]

        D1 --> D2 --> D3
    end

    CACHE[("actions/cache
    ~/.cache/ccache
    key: ccache-valhalla-{ref_slug}")]

    RADDATA[("valhalla/RAD-data
    diffs/{run_id}.json")]

    O1 <-->|restore / save| CACHE
    N1 <-->|restore / save| CACHE
    D3 -->|git push| RADDATA
```

## Storage layout

| Data | Where | Lifetime |
|------|--------|----------|
| ccache object files | GitHub `actions/cache` | until evicted (7-day LRU) |
| pyvalhalla wheel (16MB) | `/tmp/valhalla-dist` on runner | single job |
| graph tiles tar | `/tmp/valhalla_tiles` on runner | single job |
| route responses | GHA artifact | 7 days |
| diff results | `valhalla/RAD-data` git commit | permanent |
