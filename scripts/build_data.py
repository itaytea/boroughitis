"""
Boroughitis data builder.

Downloads NJ county subdivision shapefile from Census TIGER/Line + 2020
population from the Census API. Outputs:

  data/municipalities.json   -- 564 munis: id, name, type, county, population,
                                centroid, borders
  data/counties.json         -- county adjacency map
  data/outlines/<id>.svg     -- one normalized SVG per muni

Run once; rerun only if NJ creates/dissolves a municipality (rare).
"""

from __future__ import annotations

import io
import json
import math
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

# --- config ---------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
OUTLINES_DIR = DATA_DIR / "outlines"
CACHE_DIR = Path(__file__).resolve().parent / "_cache"

TIGER_YEAR = 2023  # last full-year release as of script authoring
TIGER_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/COUSUB/"
    f"tl_{TIGER_YEAR}_34_cousub.zip"
)
COUNTY_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/COUNTY/"
    f"tl_{TIGER_YEAR}_us_county.zip"
)
import os
_CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "").strip()
POP_URL = (
    "https://api.census.gov/data/2020/dec/pl"
    "?get=NAME,P1_001N&for=county%20subdivision:*&in=state:34"
    + (f"&key={_CENSUS_KEY}" if _CENSUS_KEY else "")
)

# NJ State Plane (NAD83 / NJ ftUS) -- good for shape + adjacency in NJ
NJ_CRS = "EPSG:3424"

# County FIPS -> name (NJ has 21 counties; FIPS codes are stable)
NJ_COUNTY_NAMES = {
    "001": "Atlantic",   "003": "Bergen",     "005": "Burlington",
    "007": "Camden",     "009": "Cape May",   "011": "Cumberland",
    "013": "Essex",      "015": "Gloucester", "017": "Hudson",
    "019": "Hunterdon",  "021": "Mercer",     "023": "Middlesex",
    "025": "Monmouth",   "027": "Morris",     "029": "Ocean",
    "031": "Passaic",    "033": "Salem",      "035": "Somerset",
    "037": "Sussex",     "039": "Union",      "041": "Warren",
}

SVG_BOX = 100
SVG_PAD = 4


# --- helpers --------------------------------------------------------------

def slugify(name: str, mtype: str, county: str) -> str:
    """Stable, human-readable, unique id (NJ has multiple 'Washington Township's)."""
    def clean(s: str) -> str:
        return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    return f"{clean(name)}-{clean(mtype)}-{clean(county)}"


def extract_type(namelsad: str, name: str) -> str:
    """
    TIGER NAMELSAD: 'Newark city', 'Morristown town', 'Hoboken city',
    'Loch Arbour village', 'Princeton', etc.
    Strip the name to leave the type suffix.
    """
    suffix = namelsad[len(name):].strip().lower()
    # Normalize the handful of variants seen in NJ.
    if not suffix:
        return "municipality"  # very rare; only Princeton in older data
    return suffix


def download(url: str, cache_name: str) -> bytes:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / cache_name
    if cached.exists():
        return cached.read_bytes()
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "boroughitis-builder"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    cached.write_bytes(data)
    return data


def load_shapefile(zip_bytes: bytes) -> gpd.GeoDataFrame:
    """Read a zipped shapefile from memory without unpacking to disk."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        shp_name = next(n for n in zf.namelist() if n.endswith(".shp"))
        # geopandas can read from a vsizip URL; easier: extract to tmp
        tmp = CACHE_DIR / shp_name.replace("/", "_").replace(".shp", "")
        tmp.mkdir(parents=True, exist_ok=True)
        for n in zf.namelist():
            (tmp / Path(n).name).write_bytes(zf.read(n))
        return gpd.read_file(tmp / Path(shp_name).name)


def polygon_to_svg_path(geom, bbox) -> str:
    """
    Convert a (Multi)Polygon in NJ State Plane to an SVG path string,
    normalized into a SVG_BOX x SVG_BOX viewBox with SVG_PAD padding.
    """
    minx, miny, maxx, maxy = bbox
    w = maxx - minx
    h = maxy - miny
    span = max(w, h) or 1
    # Center within the box.
    scale = (SVG_BOX - 2 * SVG_PAD) / span
    off_x = SVG_PAD + ((SVG_BOX - 2 * SVG_PAD) - w * scale) / 2
    off_y = SVG_PAD + ((SVG_BOX - 2 * SVG_PAD) - h * scale) / 2

    def tx(x, y):
        # Flip y so north is up.
        return (x - minx) * scale + off_x, (SVG_BOX - off_y) - (y - miny) * scale

    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    parts: List[str] = []
    for poly in polys:
        rings = [poly.exterior] + list(poly.interiors)
        for ring in rings:
            coords = list(ring.coords)
            if not coords:
                continue
            x0, y0 = tx(*coords[0])
            d = [f"M{x0:.2f},{y0:.2f}"]
            for x, y in coords[1:]:
                px, py = tx(x, y)
                d.append(f"L{px:.2f},{py:.2f}")
            d.append("Z")
            parts.append(" ".join(d))
    return " ".join(parts)


def write_svg(path: Path, d: str) -> None:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SVG_BOX} {SVG_BOX}">'
        f'<path d="{d}" fill="currentColor" stroke="currentColor" '
        f'stroke-width="0.5" stroke-linejoin="round"/></svg>'
    )
    path.write_text(svg)


# --- main pipeline --------------------------------------------------------

def build():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTLINES_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/6] downloading TIGER county-subdivisions for NJ")
    cousub_zip = download(TIGER_URL, f"tl_{TIGER_YEAR}_34_cousub.zip")
    munis = load_shapefile(cousub_zip)
    print(f"      loaded {len(munis)} county subdivisions")

    print("[2/6] downloading 2020 Census population")
    pop_raw = download(POP_URL, "nj_pop_2020.json").decode()
    try:
        pop_rows = json.loads(pop_raw)
    except json.JSONDecodeError:
        snippet = pop_raw[:200].replace("\n", " ")
        if "Missing Key" in pop_raw or "key" in pop_raw.lower():
            raise SystemExit(
                "\nCensus API now requires a free API key.\n"
                "  1. Sign up: https://api.census.gov/data/key_signup.html\n"
                "  2. Run:    export CENSUS_API_KEY=your_key_here\n"
                "  3. Delete cache: rm scripts/_cache/nj_pop_2020.json\n"
                "  4. Rerun:   python3 scripts/build_data.py\n"
            )
        raise SystemExit(f"\nUnexpected response from Census API:\n{snippet}\n")
    pop_df = pd.DataFrame(pop_rows[1:], columns=pop_rows[0])
    pop_df["GEOID"] = pop_df["state"] + pop_df["county"] + pop_df["county subdivision"]
    pop_df["population"] = pd.to_numeric(pop_df["P1_001N"])
    pop_df = pop_df[["GEOID", "population"]]

    # Join + filter
    munis = munis.merge(pop_df, on="GEOID", how="left")
    # Drop any "0" / unorganized entries. NJ shouldn't have these but be safe.
    before = len(munis)
    munis = munis[munis["NAME"].notna() & (munis["NAME"].str.lower() != "county subdivisions not defined")]
    munis = munis[munis["population"].fillna(0) > 0]
    print(f"      after filter: {len(munis)} munis (dropped {before - len(munis)})")

    print(f"[3/6] reprojecting to {NJ_CRS} for adjacency + shapes")
    munis = munis.to_crs(NJ_CRS).reset_index(drop=True)

    # Build records (without borders yet -- need slug map first).
    records = []
    for i, row in munis.iterrows():
        county_name = NJ_COUNTY_NAMES.get(row["COUNTYFP"], f"County{row['COUNTYFP']}")
        mtype = extract_type(row["NAMELSAD"], row["NAME"])
        slug = slugify(row["NAME"], mtype, county_name)
        records.append({
            "idx": i,
            "id": slug,
            "name": row["NAME"],
            "type": mtype,
            "county": county_name,
            "population": int(row["population"]),
            "_geom": row.geometry,
        })

    # Sanity: slugs unique?
    seen: Dict[str, int] = defaultdict(int)
    for r in records:
        seen[r["id"]] += 1
    dupes = [k for k, v in seen.items() if v > 1]
    if dupes:
        raise RuntimeError(f"duplicate slugs: {dupes[:10]}")

    idx_to_slug = {r["idx"]: r["id"] for r in records}

    print("[4/6] computing centroids + adjacency (spatial index)")
    # Centroids: in WGS84 lat/lng for the direction calc on the client.
    centroids_wgs = gpd.GeoSeries([r["_geom"].centroid for r in records],
                                  crs=NJ_CRS).to_crs("EPSG:4326")

    sindex = munis.sindex
    borders_by_idx: Dict[int, List[str]] = defaultdict(list)
    for i, row in munis.iterrows():
        # Candidates whose bbox intersects ours.
        cand = list(sindex.intersection(row.geometry.bounds))
        for j in cand:
            if j == i:
                continue
            # 'touches' = shared boundary, no interior overlap. Strict adjacency.
            # Use intersects + shape filter as fallback because tiny float gaps
            # in TIGER polygons sometimes break .touches(). Practical heuristic:
            # share a boundary of nonzero length.
            other = munis.iloc[j].geometry
            inter = row.geometry.boundary.intersection(other.boundary)
            if not inter.is_empty and inter.length > 0.5:  # > 0.5 ft shared edge
                borders_by_idx[i].append(idx_to_slug[j])

    print(f"      avg neighbors per muni: "
          f"{sum(len(v) for v in borders_by_idx.values()) / len(records):.1f}")

    print("[5/6] writing SVG outlines")
    for r in records:
        geom = r["_geom"]
        bbox = geom.bounds
        d = polygon_to_svg_path(geom, bbox)
        write_svg(OUTLINES_DIR / f"{r['id']}.svg", d)

    print("[6/6] deriving county adjacency + writing JSON")
    # Two counties are adjacent if any of their munis border each other.
    muni_county = {r["id"]: r["county"] for r in records}
    county_adj: Dict[str, set] = defaultdict(set)
    for i, neighbors in borders_by_idx.items():
        my_county = muni_county[idx_to_slug[i]]
        for nslug in neighbors:
            n_county = muni_county[nslug]
            if n_county != my_county:
                county_adj[my_county].add(n_county)
                county_adj[n_county].add(my_county)

    # Final municipality records.
    out_munis = []
    for r in records:
        c = centroids_wgs.iloc[r["idx"]]
        out_munis.append({
            "id": r["id"],
            "name": r["name"],
            "type": r["type"],
            "county": r["county"],
            "population": r["population"],
            "centroid": [round(c.y, 5), round(c.x, 5)],  # [lat, lng]
            "borders": sorted(borders_by_idx[r["idx"]]),
        })

    out_munis.sort(key=lambda m: m["name"])
    (DATA_DIR / "municipalities.json").write_text(
        json.dumps(out_munis, indent=2)
    )

    counties_out = {c: sorted(list(adj)) for c, adj in county_adj.items()}
    # Ensure all 21 counties present, even those with no neighbors (none in NJ).
    for c in NJ_COUNTY_NAMES.values():
        counties_out.setdefault(c, [])
    (DATA_DIR / "counties.json").write_text(
        json.dumps(counties_out, indent=2, sort_keys=True)
    )

    print(f"\nDONE. {len(out_munis)} municipalities, "
          f"{sum(len(v) for v in counties_out.values()) // 2} county adjacencies, "
          f"{len(list(OUTLINES_DIR.glob('*.svg')))} SVG outlines.")


if __name__ == "__main__":
    build()
