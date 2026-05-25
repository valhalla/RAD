"""CLI entry point for the Valhalla RAD route generator."""

import argparse
import random
import sys
from pathlib import Path

from route_generator.generator import build_requests, load_switzerland_polygon, write_jsonl


def main() -> None:
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
        help="Number of route requests to generate (default: 1000)",
    )
    args = parser.parse_args()

    if args.count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
        sys.exit(1)

    seed = random.randint(0, 2**32 - 1)
    rng = random.Random(seed)

    polygon = load_switzerland_polygon()
    requests = build_requests(n_pairs=args.count, polygon=polygon, rng=rng)
    write_jsonl(requests, args.output)
    print(f"Written requests to {args.output}")


if __name__ == "__main__":
    main()
