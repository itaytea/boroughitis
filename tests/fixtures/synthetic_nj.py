"""Tiny synthetic stand-in for the TIGER county-subdivision + Census inputs.

Layout (each cell is a 0.01 degree square, west to east, y=0 row unless noted):

    y=1:  [Vacant]
    y=0:  [Alpha][Bravo][Charlie][Delta]
           Essex  Essex   Union    Union

Vacant (Essex, population 0) sits on top of Alpha and must be dropped.
Only Bravo/Charlie touch across the Essex/Union county line.
"""
import json

import geopandas as gpd
from shapely.geometry import box

STEP = 0.01
LON0, LAT0 = -74.20, 40.70


def _cell(col, row):
    # Compute every edge from its own index so neighbors share exact vertices
    # (x + STEP would differ from the next cell's x by float error).
    def edge(origin, i):
        return round(origin + i * STEP, 6)

    return box(edge(LON0, col), edge(LAT0, row), edge(LON0, col + 1), edge(LAT0, row + 1))


# name, namelsad, countyfp, countysub fp, (col, row), population
ROWS = [
    ("Alpha", "Alpha borough", "013", "00010", (0, 0), 1000),
    ("Bravo", "Bravo township", "013", "00020", (1, 0), 2000),
    ("Charlie", "Charlie city", "039", "00030", (2, 0), 3000),
    ("Delta", "Delta township", "039", "00040", (3, 0), 4000),
    ("Vacant", "Vacant township", "013", "00050", (0, 1), 0),
]


def make_subdivisions():
    """GeoDataFrame shaped like the TIGER cousub shapefile (WGS84)."""
    return gpd.GeoDataFrame(
        {
            "GEOID": ["34" + r[2] + r[3] for r in ROWS],
            "NAME": [r[0] for r in ROWS],
            "NAMELSAD": [r[1] for r in ROWS],
            "COUNTYFP": [r[2] for r in ROWS],
        },
        geometry=[_cell(*r[4]) for r in ROWS],
        crs="EPSG:4326",
    )


def make_population_json():
    """Census API response body: header row followed by data rows."""
    header = ["NAME", "P1_001N", "state", "county", "county subdivision"]
    rows = [[f"{r[1]}, NJ", str(r[5]), "34", r[2], r[3]] for r in ROWS]
    return json.dumps([header] + rows).encode()
