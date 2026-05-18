# Running the data builder

You only need to do this once (and again if NJ creates a new municipality,
which happens rarely).

## 0. Get a free Census API key

The 2020 Decennial Census API requires a key (free, instant):
<https://api.census.gov/data/key_signup.html>

Then in your terminal:

```bash
export CENSUS_API_KEY=your_key_here
```

(Add this line to `~/.zshrc` to make it permanent.)

## 1. Install Python dependencies

`geopandas` has C dependencies. The easiest install on macOS:

```bash
# Option A: conda (most reliable)
conda install -c conda-forge geopandas pandas shapely

# Option B: pip (works if you already have GDAL installed via Homebrew)
brew install gdal
pip install -r scripts/requirements.txt
```

## 2. Run it

```bash
python3 scripts/build_data.py
```

Expected output:

```
[1/6] downloading TIGER county-subdivisions for NJ
      loaded ~720 county subdivisions
[2/6] downloading 2020 Census population
[3/6] reprojecting to EPSG:3424 for adjacency + shapes
      after filter: 564 munis (dropped ~150 non-muni entries)
[4/6] computing centroids + adjacency (spatial index)
      avg neighbors per muni: ~5.5
[5/6] writing SVG outlines
[6/6] deriving county adjacency + writing JSON

DONE. 564 municipalities, ~XXX county adjacencies, 564 SVG outlines.
```

Outputs land in `data/`:
- `municipalities.json`
- `counties.json`
- `outlines/*.svg` (564 files)

## 3. Verify

Spot-check a few:

```bash
python3 -c "
import json
m = json.load(open('data/municipalities.json'))
print('total:', len(m))
newark = next(x for x in m if x['name'] == 'Newark')
print('Newark borders:', newark['borders'])
"
```

Newark should border Belleville, East Orange, Elizabeth, Harrison, Hillside,
Irvington, Jersey City, Kearny, and a couple others.

---

# Playing locally

`fetch()` won't work over `file://`, so you need to serve the folder. Pick one:

```bash
# from the project root
python3 -m http.server 8765
```

Then open: <http://localhost:8765/>

The page currently runs against the **6-muni sample dataset** in `data/`.
Once you run `scripts/build_data.py`, the full 564-municipality dataset
overwrites it — no frontend changes needed.

## Notes on the sample data

The seeded sample only contains Newark, Jersey City, Hoboken, Belleville,
Bloomfield, and East Orange. The outline SVGs are placeholder shapes, not
actual municipal boundaries — they'll be replaced with real ones when
`build_data.py` runs.
