import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import make_schedule as ms  # noqa: E402

IDS = [f"m{i}" for i in range(7)]


def test_extend_two_cycle_schedule():
    two = ms.build([], IDS, seed=1, cycles=2)
    assert len(two) == 14
    out = ms.build(two, IDS, seed=2, cycles=2)
    assert out[:14] == two
    assert len(out) == 21
    for k in range(0, 21, 7):
        assert sorted(out[k:k + 7]) == sorted(IDS)


def test_partial_last_cycle_is_completed():
    prefix = ms.build([], IDS, seed=1, cycles=2)[:10]
    out = ms.build(prefix, IDS, seed=3, cycles=1)
    assert out[:10] == prefix
    assert len(out) == 14
    assert sorted(out[7:]) == sorted(IDS)


def test_repeat_within_window_rejected():
    with pytest.raises(SystemExit):
        ms.build(["m0", "m1", "m0"], IDS, seed=1, cycles=1)


def test_too_few_ids():
    with pytest.raises(SystemExit):
        ms.build([], ["a"], seed=1, cycles=1)


def test_no_adjacent_repeats():
    for seed in range(50):
        out = ms.build([], IDS, seed=seed, cycles=4)
        assert all(a != b for a, b in zip(out, out[1:]))
