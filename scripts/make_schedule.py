"""Generate data/schedule.json: a seeded, no-repeat daily muni schedule.

Existing entries in schedule.json are kept as-is (same start_date, same
day numbering); the remaining municipality ids are shuffled with a fixed
seed and appended, so every muni appears exactly once per cycle.

Usage: python3 scripts/make_schedule.py [--seed N] [--cycles K]
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def build(existing: list[str], ids: list[str], seed: int, cycles: int) -> list[str]:
    unknown = [i for i in existing if i not in set(ids)]
    if unknown:
        raise SystemExit(f"existing schedule has unknown ids: {unknown}")
    if len(set(existing)) != len(existing):
        raise SystemExit("existing schedule contains repeats")
    rng = random.Random(seed)
    out = list(existing)
    seen = set(existing)
    rest = sorted(i for i in ids if i not in seen)
    rng.shuffle(rest)
    out += rest
    for _ in range(cycles - 1):
        cycle = sorted(ids)
        rng.shuffle(cycle)
        # avoid a repeat across the cycle boundary
        if cycle[0] == out[-1]:
            cycle[0], cycle[-1] = cycle[-1], cycle[0]
        out += cycle
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260518)
    ap.add_argument("--cycles", type=int, default=1,
                    help="full passes over all munis (default 1)")
    args = ap.parse_args()

    path = DATA / "schedule.json"
    sched = json.loads(path.read_text())
    ids = [m["id"] for m in json.loads((DATA / "municipalities.json").read_text())]
    sched["munis"] = build(sched["munis"], ids, args.seed, args.cycles)
    path.write_text(json.dumps(sched, indent=2) + "\n")
    print(f"wrote {len(sched['munis'])} entries from {sched['start_date']}")


if __name__ == "__main__":
    main()
