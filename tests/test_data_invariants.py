"""Invariants for the committed data files (stdlib only, no geopandas)."""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
OUTLINES = DATA / "outlines"


@pytest.fixture(scope="module")
def munis():
    return json.loads((DATA / "municipalities.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def counties():
    return json.loads((DATA / "counties.json").read_text(encoding="utf-8"))


def test_564_unique_ids(munis):
    ids = [m["id"] for m in munis]
    assert len(ids) == 564
    assert len(set(ids)) == 564


def test_borders_valid_and_symmetric(munis):
    by_id = {m["id"]: set(m["borders"]) for m in munis}
    problems = []
    for mid, borders in by_id.items():
        if mid in borders:
            problems.append(f"{mid} borders itself")
        for b in borders:
            if b not in by_id:
                problems.append(f"{mid} -> unknown id {b}")
            elif mid not in by_id[b]:
                problems.append(f"{mid} -> {b} is not reciprocated")
    assert not problems, problems[:20]


def test_every_id_has_outline_and_no_orphans(munis):
    ids = {m["id"] for m in munis}
    files = {p.stem for p in OUTLINES.glob("*.svg")}
    assert not ids - files, f"missing outlines: {sorted(ids - files)[:20]}"
    assert not files - ids, f"orphan outlines: {sorted(files - ids)[:20]}"


def test_21_counties(counties):
    assert len(counties) == 21


def test_county_adjacency_symmetric(counties):
    problems = []
    for c, neighbours in counties.items():
        if c in neighbours:
            problems.append(f"{c} adjacent to itself")
        for n in neighbours:
            if n not in counties:
                problems.append(f"{c} -> unknown county {n}")
            elif c not in counties[n]:
                problems.append(f"{c} -> {n} is not reciprocated")
    assert not problems, problems


def test_municipality_counties_exist(munis, counties):
    bad = sorted({m["county"] for m in munis} - set(counties))
    assert not bad, bad
