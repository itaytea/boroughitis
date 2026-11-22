"""Pipeline test for build_data.build() on a tiny synthetic fixture.

Downloads and the shapefile reader are monkeypatched, and output goes to a
tmp dir, so there is no network and no writes to the real data/ folder.
"""
import json
import os
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_data as bd  # noqa: E402
from fixtures import synthetic_nj  # noqa: E402


@pytest.fixture
def built(tmp_path, monkeypatch):
    def fake_download(url, cache_name):
        if url == bd.TIGER_URL:
            return b"fake-zip"
        if url == bd.POP_URL:
            return synthetic_nj.make_population_json()
        raise AssertionError(f"unexpected download: {url}")

    monkeypatch.setattr(bd, "download", fake_download)
    monkeypatch.setattr(bd, "load_shapefile", lambda _b: synthetic_nj.make_subdivisions())
    monkeypatch.setattr(bd, "DATA_DIR", tmp_path)
    monkeypatch.setattr(bd, "OUTLINES_DIR", tmp_path / "outlines")
    bd.build()
    munis = json.loads((tmp_path / "municipalities.json").read_text())
    counties = json.loads((tmp_path / "counties.json").read_text())
    return tmp_path, munis, counties


def test_zero_population_entry_is_dropped(built):
    tmp, munis, _ = built
    assert [m["name"] for m in munis] == ["Alpha", "Bravo", "Charlie", "Delta"]
    assert not (tmp / "outlines" / "vacant-township-essex.svg").exists()


def test_muni_adjacency(built):
    _, munis, _ = built
    borders = {m["id"]: m["borders"] for m in munis}
    assert borders == {
        "alpha-borough-essex": ["bravo-township-essex"],
        "bravo-township-essex": ["alpha-borough-essex", "charlie-city-union"],
        "charlie-city-union": ["bravo-township-essex", "delta-township-union"],
        "delta-township-union": ["charlie-city-union"],
    }


def test_county_adjacency(built):
    _, _, counties = built
    assert counties["Essex"] == ["Union"]
    assert counties["Union"] == ["Essex"]
    # every NJ county is still present, with no neighbors in the fixture
    assert set(counties) == set(bd.NJ_COUNTY_NAMES.values())
    assert counties["Bergen"] == []


def test_output_schema(built):
    tmp, munis, counties = built
    keys = {"id", "name", "type", "county", "population", "centroid", "borders"}
    for m in munis:
        assert set(m) == keys
        assert isinstance(m["population"], int) and m["population"] > 0
        assert len(m["centroid"]) == 2
        lat, lng = m["centroid"]
        assert 40.7 < lat < 40.72 and -74.2 < lng < -74.15
        assert (tmp / "outlines" / f"{m['id']}.svg").exists()
    assert [m["type"] for m in munis] == ["borough", "township", "city", "township"]
    assert [m["county"] for m in munis] == ["Essex", "Essex", "Union", "Union"]
    assert all(isinstance(v, list) for v in counties.values())
    assert len(list((tmp / "outlines").glob("*.svg"))) == 4
