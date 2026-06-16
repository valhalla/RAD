#!/usr/bin/env python3
"""
Usage:
  python3 scripts/run_routes.py \
    --config /tmp/valhalla.json \
    --requests RAD-data/requests/requests.jsonl \
    --output /tmp/responses-old.jsonl
"""

import argparse
import json

import valhalla


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--requests", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    config = args.config
    actor = valhalla.Actor(config)

    with open(args.requests) as req_f, open(args.output, "w") as out_f:
        for line in req_f:
            request = json.loads(line)
            try:
                response = json.loads(actor.route(json.dumps(request)))
                status = "ok"
            except Exception as e:
                response = {"error": str(e)}
                status = "error"
            out_f.write(json.dumps({"request": request, "response": response, "status": status}) + "\n")


if __name__ == "__main__":
    main()
