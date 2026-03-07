# golf-course-3d-generator

> Automate the generation of 3D-printable par-3 golf hole models from
> publicly available Digital Terrain Model (DTM) data.

---

## Overview

This Docker-based tool takes a **GeoTIFF / VRT elevation raster** (DTM/DEM)
or a **directory of DTM tile files** and golf hole geometry from
**OpenStreetMap** and produces watertight **STL** meshes ready to send to a
3D printer.  The intended output is a commemorative *Hole in One* plaque or
desk ornament that captures the real terrain of a par-3 hole.

```
DTM tiles ─► VRT index ─┐
                          ├──► clip ──► mesh layers ──► STL × 3
OSM hole data ────────────┘
```

### Key features

| Feature | Detail |
|---------|--------|
| Input formats | Single GeoTIFF / VRT **or** directory of `.img` tiles |
| Multi-tile indexing | `index.vrt` built automatically with `gdalbuildvrt` |
| Coordinate crop | `--lat` / `--lon` selects a 200 m × 200 m study area |
| Golf course data | OpenStreetMap Overpass API (automatic) |
| Output formats | **STL** (single or layered), OBJ |
| Layered output | Three STLs for multi-material / filament-swap printing |
| Vertical exaggeration | Configurable `--z-scale` |
| Print-bed sizing | `--target-size` rescales to a given mm dimension |
| Solid base | Configurable `--base-thickness` for a printable solid |
| Docker | Fully containerised; no local Python setup needed |

---

## Quick start (Docker)

### 1. Obtain a DTM file

Download a GeoTIFF (or a package of `.img` tiles) covering your golf course
from any public source, e.g.

- **USGS 3DEP** – <https://apps.nationalmap.gov/downloader/>
- **Copernicus DEM** – <https://spacedata.copernicus.eu/>
- **OpenTopography** – <https://opentopography.org/>
- **Natural Resources Canada (GeoGratis)** – <https://maps.canada.ca/czs/index-en.html>  
  Select *Digital Elevation* → *CDEM* (Canadian DEM, 20 m) or *HRDEM* (High-Resolution DEM, 1 m where available).
- **Ontario GeoHub (LiDAR-derived DEM)** – <https://geohub.lio.gov.on.ca/>  
  Search for *"Digital Elevation Model"* or *"LiDAR"*; Ontario Ministry of Natural Resources provides
  0.5 m – 1 m resolution tiles for most of the province (e.g. the Milton Package with 249 `.img` files).

**Single-file layout:**
```
data/
└── terrain.tif
```

**Multi-tile layout** (e.g. Ontario Milton DTM package):
```
data/
└── milton/
    ├── tile_001.img
    ├── tile_002.img
    └── …  (249 tiles)
```
An `index.vrt` is created automatically in the same directory the first time
you run the tool.

### 2. Find the OSM way ID

1. Go to <https://www.openstreetmap.org/> and navigate to your golf course.
2. Click the *Query features* tool and click on the par-3 hole outline.
3. Note the **Way ID** (e.g. `123456789`).

### 3. Build and run

```bash
# Build the image (first time only)
docker compose build

# Single-file mode: generate one STL from a GeoTIFF
docker compose run --rm generator generate \
    --dtm /data/terrain.tif \
    --hole-id 123456789 \
    --output /output/hole3.stl

# Multi-tile mode: auto-index .img tiles, crop to coordinate, output 3 STLs
docker compose run --rm generator generate \
    --dtm-dir /data/milton \
    --hole-id 123456789 \
    --lat 43.5123 --lon -79.8765 \
    --output /output/hole3_layers
```

The multi-tile output directory contains:

| File | 3D Print purpose |
|------|-----------------|
| `base_terrain.stl` | Main structural body |
| `green_inlay.stl` | Green / tee colour insert |
| `bunker_cutout.stl` | Sand / bunker filament inlay |

Import all three into Bambu Studio or PrusaSlicer as a **multi-part object**
and assign a different filament to each part.

Pass `--output /output/hole3_layers.zip` to receive a single ZIP archive
instead of a directory.

### 4. Generate all par-3 holes near a coordinate

```bash
docker compose run --rm generator generate-all \
    --dtm /data/terrain.tif \
    --lat 40.7128 --lon -74.0060 \
    --radius 3000 \
    --output-dir /output
```

---

## CLI reference

```
Usage: python -m src.main [OPTIONS] COMMAND [ARGS]...

  Automate generation of 3D-printable par-3 golf hole models from DTM data.

Commands:
  generate      Generate a 3D model for a single par-3 hole (by OSM way ID).
  generate-all  Find all par-3 holes near LAT/LON and generate a model each.
```

### `generate` options

| Option | Default | Description |
|--------|---------|-------------|
| `--dtm PATH` | *one of dtm / dtm-dir required* | Single GeoTIFF or VRT file |
| `--dtm-dir PATH` | *one of dtm / dtm-dir required* | Directory of `.img` tile files; `index.vrt` built automatically |
| `--lat FLOAT` | *required with `--dtm-dir`* | Latitude of study-area centre (WGS-84) |
| `--lon FLOAT` | *required with `--dtm-dir`* | Longitude of study-area centre (WGS-84) |
| `--hole-id INT` | *required* | OpenStreetMap way ID (`golf=hole`) |
| `--buffer FLOAT` | `50` | Buffer in metres around the hole boundary |
| `--base-thickness FLOAT` | `3.0` | Solid base thickness (metres) |
| `--z-scale FLOAT` | `1.5` | Vertical exaggeration factor |
| `--target-size FLOAT` | *none* | Rescale longest XY dimension to this mm value |
| `--output PATH` | `hole.stl` | Single-file mode: `.stl` / `.obj` path.  Multi-tile mode: directory or `.zip` path |

### `generate-all` options

All of the above `--dtm` / mesh options plus:

| Option | Default | Description |
|--------|---------|-------------|
| `--lat FLOAT` | *required* | Latitude of search centre |
| `--lon FLOAT` | *required* | Longitude of search centre |
| `--radius FLOAT` | `5000` | Search radius in metres |
| `--output-dir PATH` | `output` | Directory for output files |
| `--format {stl,obj}` | `stl` | Output file format |

---

## Running without Docker

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt-get install gdal-bin libgdal-dev libspatialindex-dev

# Install Python dependencies
pip install -r requirements.txt

# Single-file mode
python -m src.main generate \
    --dtm data/terrain.tif \
    --hole-id 123456789 \
    --output output/hole.stl

# Multi-tile mode
python -m src.main generate \
    --dtm-dir data/milton \
    --hole-id 123456789 \
    --lat 43.5123 --lon -79.8765 \
    --output output/hole_layers
```

---

## Development

### Project layout

```
golf-course-3d-generator/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py            # Click CLI entry point (registers sub-commands)
│   ├── pipeline.py        # Core pipeline: buffer + clip + mesh + export
│   ├── dtm_processor.py   # GeoTIFF / VRT loading & clipping
│   ├── vrt_builder.py     # Multi-tile VRT index builder (gdalbuildvrt)
│   ├── course_fetcher.py  # OpenStreetMap Overpass queries
│   ├── mesh_generator.py  # Elevation → watertight 3-D mesh (+ layer support)
│   ├── exporter.py        # STL / OBJ / ZIP export
│   └── commands/
│       ├── __init__.py
│       ├── options.py      # Shared Click option decorators
│       ├── generate.py     # `generate` sub-command
│       └── generate_all.py # `generate-all` sub-command
├── tests/
│   ├── test_dtm_processor.py
│   ├── test_mesh_generator.py
│   ├── test_mesh_generator_layers.py
│   ├── test_vrt_builder.py
│   ├── test_course_fetcher.py
│   └── test_exporter.py
├── data/      # Place your DTM GeoTIFFs / tile directories here (not committed)
└── output/    # Generated STL / OBJ files (not committed)
```

### Running tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Overpass API endpoint (override for self-hosted instance) |

---

## Pipeline details

1. **VRT Builder** (`src/vrt_builder.py`)  
   When `--dtm-dir` is provided, scans the directory for `.img` tile files
   and runs `gdalbuildvrt -overwrite` to create `index.vrt`.  An existing
   VRT is reused on subsequent runs without rebuilding.

2. **DTM Processor** (`src/dtm_processor.py`)  
   Opens a GeoTIFF or VRT with `rasterio`, reprojects the hole geometry into
   the raster's CRS, and returns a clipped NumPy elevation array.

3. **Course Fetcher** (`src/course_fetcher.py`)  
   Queries the OpenStreetMap Overpass API for `golf=hole` ways tagged
   `par=3`.  Returns Shapely polygons in WGS-84.

4. **Mesh Generator** (`src/mesh_generator.py`)  
   Converts the elevation grid to watertight trimesh solids:
   - `generate()` – single full-terrain mesh (backward-compatible).
   - `generate_layers()` – three meshes for multi-material printing:
     - *base_terrain*: full terrain (structural body).
     - *green_inlay*: flat elevated plateaus (low slope + Z ≥ median).
     - *bunker_cutout*: local depressions (Z < median − 0.5 × std).

5. **Exporter** (`src/exporter.py`)  
   Writes the mesh to STL (default) or OBJ.  For layered output:
   - `export_layers_to_dir()` – three `<name>.stl` files in a directory.
   - `export_layers_to_zip()` – a single ZIP archive containing the three STLs.

---

## License

MIT – see [LICENSE](LICENSE).
