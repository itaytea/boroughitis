"""Integrity checks for data/schedule.json and scripts/make_schedule.py.

Stdlib only (no geopandas), so these always run, including in CI.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_schedule as ms  # noqa: E402

MIN_DAYS_REMAINING = 180

SCHEDULE = json.loads((ROOT / "data" / "schedule.json").read_text())
MUNI_IDS = [m["id"] for m in json.loads((ROOT / "data" / "municipalities.json").read_text())]
ENTRIES = SCHEDULE["munis"]


def test_start_date_parses():
    assert isinstance(SCHEDULE["start_date"], str)
    date.fromisoformat(SCHEDULE["start_date"])


def test_all_ids_exist_in_municipalities():
    known = set(MUNI_IDS)
    unknown = [i for i in ENTRIES if i not in known]
    assert not unknown, f"unknown ids in schedule: {unknown[:5]}"


def test_no_repeats_within_a_cycle():
    n = len(MUNI_IDS)
    for start in range(0, len(ENTRIES), n):
        cycle = ENTRIES[start:start + n]
        dupes = {i for i in cycle if cycle.count(i) > 1}
        assert not dupes, f"repeats in cycle starting at day {start}: {sorted(dupes)[:5]}"


def test_no_id_twice_in_a_row():
    for day in range(1, len(ENTRIES)):
        assert ENTRIES[day] != ENTRIES[day - 1], f"repeat on day {day}: {ENTRIES[day]}"


def test_build_keeps_existing_prefix():
    for cycles in (1, 2):
        out = ms.build(list(ENTRIES), MUNI_IDS, seed=1, cycles=cycles)
        assert out[:len(ENTRIES)] == ENTRIES
        assert len(out) >= len(ENTRIES)
    # a partial prefix is also preserved, and the result covers every muni
    prefix = ENTRIES[:10]
    out = ms.build(prefix, MUNI_IDS, seed=1, cycles=1)
    assert out[:10] == prefix
    assert sorted(out) == sorted(MUNI_IDS)


def test_enough_days_remain():
    start = date.fromisoformat(SCHEDULE["start_date"])
    last = start + timedelta(days=len(ENTRIES) - 1)
    remaining = (last - date.today()).days
    assert remaining >= MIN_DAYS_REMAINING, (
        f"schedule ends {last} ({remaining} days left, need {MIN_DAYS_REMAINING}); "
        "run scripts/make_schedule.py --cycles N to extend it"
    )
