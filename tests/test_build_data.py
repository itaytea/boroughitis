"""Tests for the pure helpers in scripts/build_data.py (no network, no cache)."""
import os
import re
import sys
from pathlib import Path

import pytest

# In CI (CI_REQUIRE_DEPS=1) missing build deps must fail, not silently skip.
if os.environ.get("CI_REQUIRE_DEPS") == "1":
    import geopandas  # noqa: F401
    import shapely  # noqa: F401
else:
    pytest.importorskip("geopandas")
    pytest.importorskip("shapely")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_data as bd  # noqa: E402
from shapely.geometry import MultiPolygon, Polygon  # noqa: E402


# --- slugify ---------------------------------------------------------------

def test_slugify_basic():
    assert bd.slugify("Newark", "city", "Essex") == "newark-city-essex"


def test_slugify_punctuation_and_spaces():
    assert bd.slugify("Washington", "township", "Cape May") == "washington-township-cape-may"
    assert bd.slugify("St. Mary's", "borough", "Union") == "st--mary-s-borough-union"


def test_slugify_disambiguates_same_name():
    a = bd.slugify("Washington", "township", "Warren")
    b = bd.slugify("Washington", "township", "Morris")
    assert a != b


def test_slugify_strips_edge_dashes():
    assert bd.slugify("-X-", "city", "Y") == "x-city-y"


# --- extract_type ----------------------------------------------------------

@pytest.mark.parametrize(
    "namelsad,name,expected",
    [
        ("Newark city", "Newark", "city"),
        ("Loch Arbour village", "Loch Arbour", "village"),
        ("Washington township", "Washington", "township"),
        ("Princeton", "Princeton", "municipality"),
        ("Morristown Town", "Morristown", "town"),
    ],
)
def test_extract_type(namelsad, name, expected):
    assert bd.extract_type(namelsad, name) == expected


# --- polygon_to_svg_path ---------------------------------------------------

def _coords(path):
    return [(float(x), float(y)) for x, y in re.findall(r"[ML]([\d.\-]+),([\d.\-]+)", path)]


def test_svg_path_square_fits_box_with_padding():
    sq = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    d = bd.polygon_to_svg_path(sq, sq.bounds)
    pts = _coords(d)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert min(xs) == pytest.approx(bd.SVG_PAD)
    assert max(xs) == pytest.approx(bd.SVG_BOX - bd.SVG_PAD)
    assert min(ys) == pytest.approx(bd.SVG_PAD)
    assert max(ys) == pytest.approx(bd.SVG_BOX - bd.SVG_PAD)
    assert d.startswith("M") and d.endswith("Z")


def test_svg_path_rounds_to_two_decimals():
    tri = Polygon([(0, 0), (3, 0), (1, 7)])
    d = bd.polygon_to_svg_path(tri, tri.bounds)
    for tok in re.findall(r"[\d.]+", d):
        if "." in tok:
            assert len(tok.split(".")[1]) == 2


def test_svg_path_north_is_up():
    tri = Polygon([(0, 0), (10, 0), (5, 10)])  # apex at north
    pts = _coords(bd.polygon_to_svg_path(tri, tri.bounds))
    apex = max(pts, key=lambda p: -p[1])  # smallest svg y
    assert apex[0] == pytest.approx(50.0)


def test_svg_path_wide_shape_is_centered_vertically():
    rect = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
    pts = _coords(bd.polygon_to_svg_path(rect, rect.bounds))
    ys = [p[1] for p in pts]
    assert (min(ys) + max(ys)) / 2 == pytest.approx(bd.SVG_BOX / 2)


def test_svg_path_multipolygon_and_holes():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hole = [(3, 3), (3, 6), (6, 6), (6, 3)]
    p1 = Polygon(outer, [hole])
    p2 = Polygon([(20, 0), (25, 0), (25, 5), (20, 5)])
    mp = MultiPolygon([p1, p2])
    d = bd.polygon_to_svg_path(mp, mp.bounds)
    assert d.count("M") == 3  # two exteriors + one interior
    assert d.count("Z") == 3


def test_svg_path_degenerate_bbox_does_not_divide_by_zero():
    p = Polygon([(1, 1), (1, 1), (1, 1)])
    d = bd.polygon_to_svg_path(p, p.bounds)
    assert isinstance(d, str)


# --- write_svg -------------------------------------------------------------

def test_write_svg_output_shape(tmp_path):
    out = tmp_path / "x.svg"
    bd.write_svg(out, "M0,0 L1,1 Z")
    text = out.read_text()
    assert text.startswith("<svg")
    assert text.endswith("</svg>")
    assert 'viewBox="0 0 100 100"' in text
    assert 'd="M0,0 L1,1 Z"' in text


# --- constants -------------------------------------------------------------

def test_county_names_cover_21_counties():
    assert len(bd.NJ_COUNTY_NAMES) == 21
    assert all(re.fullmatch(r"\d{3}", k) for k in bd.NJ_COUNTY_NAMES)
    assert len(set(bd.NJ_COUNTY_NAMES.values())) == 21
