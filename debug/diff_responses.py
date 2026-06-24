#!/usr/bin/env python3
"""
Usage:
  python3 scripts/diff_responses.py \
    --old /tmp/responses/responses-old/responses-old.jsonl \
    --new /tmp/responses/responses-new/responses-new.jsonl \
    --old-ref master \
    --new-ref feature-branch \
    --output RAD-data/diffs/12345678.json
"""

import argparse
import json
from datetime import UTC, datetime


def load_jsonl(path):
    return [json.loads(line) for line in open(path)]


def diff_entry(old, new):
    # TODO: expand with geometry comparison, maneuver diffs, etc.
    old_dur = old["response"].get("trip", {}).get("summary", {}).get("time", None)
    new_dur = new["response"].get("trip", {}).get("summary", {}).get("time", None)
    return {
        "request": old["request"],
        "old_duration": old_dur,
        "new_duration": new_dur,
        "duration_delta_s": (new_dur - old_dur) if (old_dur and new_dur) else None,
        "old_status": old["status"],
        "new_status": new["status"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--old-ref", required=True)
    p.add_argument("--new-ref", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    old_rows = load_jsonl(args.old)
    new_rows = load_jsonl(args.new)

    diffs = [diff_entry(o, n) for o, n in zip(old_rows, new_rows, strict=False)]
    changed = [d for d in diffs if d["duration_delta_s"] not in (None, 0)]

    result = {
        "meta": {
            "old_ref": args.old_ref,
            "new_ref": args.new_ref,
            "generated_at": datetime.now(UTC).isoformat(),
            "total_requests": len(diffs),
            "changed_routes": len(changed),
        },
        "diffs": diffs,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Done: {len(changed)}/{len(diffs)} routes changed")


if __name__ == "__main__":
    main()
