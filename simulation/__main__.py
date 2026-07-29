from __future__ import annotations

import argparse
import json
import logging
import sys

from simulation.generate_daily import run_daily_batch_iso
from simulation.scenarios import documented_scenarios

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load one simulated business day into Postgres (idempotent per batch_date).")
    p.add_argument("--date", help="Business date YYYY-MM-DD (required unless --list-scenarios).")
    p.add_argument("--scenario", default=None, help="Override scenario id (default: weighted random draw).")
    p.add_argument("--seed", type=int, default=None, help="Random seed (default: derived from date).")
    p.add_argument("--list-scenarios", action="store_true", help="Print scenario JSON catalogue and exit.")
    args = p.parse_args(argv)

    if args.list_scenarios:
        print(json.dumps(documented_scenarios(), indent=2))
        return 0

    if not args.date:
        p.error("--date YYYY-MM-DD is required")

    summary = run_daily_batch_iso(args.date, scenario=args.scenario, seed=args.seed)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
