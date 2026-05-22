"""
CLI entry point for the Valhalla RAD route generator.

Usage:
    uv run route-generator [--output PATH] [--count N] [--seed INT]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from route_generator.generator import build_requests, load_switzerland_polygon, write_jsonl


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate randomized Valhalla /route requests as a JSONL file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("requests.jsonl"),
        help="Path to write the output JSONL file (default: requests.jsonl)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of origin/destination coordinate pairs to generate (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible output",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
        sys.exit(1)

    # If no seed given, generate one and surface it — user needs it to reproduce this output
    seed = args.seed if args.seed is not None else random.randint(0, 2**32 - 1)
    rng = random.Random(seed)

    polygon = load_switzerland_polygon()
    requests = build_requests(n_pairs=args.count, polygon=polygon, rng=rng)
    n_written = write_jsonl(requests, args.output)

    print(f"Written {n_written} requests to {args.output} (seed={seed})")


if __name__ == "__main__":
    main()
