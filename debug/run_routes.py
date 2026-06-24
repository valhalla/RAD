#!/usr/bin/env python3
"""
Usage:
  python3 scripts/run_routes.py \
    --tile-extract /path/to/tiles.tar \
    --requests RAD-data/requests/requests.jsonl \
    --output /tmp/responses-old.jsonl
"""

import argparse
import json
from pathlib import Path

from valhalla import Actor, ValhallaError
from valhalla.config import _sanitize_config, default_config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tile-extract", required=True, help="Path to a built Valhalla tile extract (.tar)")
    p.add_argument("--requests", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    config = _sanitize_config(default_config.copy())
    config["mjolnir"]["tile_extract"] = str(Path(args.tile_extract).resolve())
    config["mjolnir"]["tile_dir"] = ""
    actor = Actor(config)

    with open(args.requests) as req_f, open(args.output, "w") as out_f:
        for line in req_f:
            request = json.loads(line)
            try:
                response = actor.route(request)
                status = "ok"
            except ValhallaError as e:
                response = {"error": str(e)}
                status = "error"
            out_f.write(json.dumps({"request": request, "response": response, "status": status}) + "\n")


if __name__ == "__main__":
    main()
