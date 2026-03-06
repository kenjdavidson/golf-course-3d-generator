# golf-course-3d-generator

> Automate the generation of 3D-printable par-3 golf hole models from
> publicly available Digital Terrain Model (DTM) data.

---

## Overview

This Docker-based tool takes a **GeoTIFF elevation raster** (DTM/DEM) and
golf hole geometry from **OpenStreetMap** and produces a watertight **STL**
(or OBJ) mesh ready to send to a 3D printer.  The intended output is a
commemorative *Hole in One* plaque or desk ornament that captures the real
terrain of a par-3 hole.

```
DTM (GeoTIFF)  ──┐
                  ├──► clip ──► mesh ──► STL
OSM hole data ───┘
```

### Key features

| Feature | Detail |
|---------|--------|
| Input formats | GeoTIFF DTM/DEM (any CRS supported by GDAL) |
| Golf course data | OpenStreetMap Overpass API (automatic) |
| Output formats | **STL**, OBJ |
| Vertical exaggeration | Configurable `--z-scale` |
| Print-bed sizing | `--target-size` rescales to a given mm dimension |
| Solid base | Configurable `--base-thickness` for a printable solid |
| Docker | Fully containerised; no local Python setup needed |

---

## Quick start (Docker)

### 1. Obtain a DTM file

Download a GeoTIFF covering your golf course from any public source, e.g.

- **USGS 3DEP** – <https://apps.nationalmap.gov/downloader/>
- **Copernicus DEM** – <https://spacedata.copernicus.eu/>
- **OpenTopography** – <https://opentopography.org/>

Place the file in the `data/` directory:

```
data/
└── terrain.tif
```

### 2. Find the OSM way ID

1. Go to <https://www.openstreetmap.org/> and navigate to your golf course.
2. Click the *Query features* tool and click on the par-3 hole outline.
3. Note the **Way ID** (e.g. `123456789`).

### 3. Build and run

```bash
# Build the image (first time only)
docker compose build

# Generate a single par-3 hole
docker compose run --rm generator generate \
    --dtm /data/terrain.tif \
    --hole-id 123456789 \
    --output /output/hole3.stl

# The STL file will be written to ./output/hole3.stl
```

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
| `--dtm PATH` | *required* | GeoTIFF DTM/DEM raster file |
| `--hole-id INT` | *required* | OpenStreetMap way ID (`golf=hole`) |
| `--buffer FLOAT` | `50` | Buffer in metres around the hole boundary |
| `--base-thickness FLOAT` | `3.0` | Solid base thickness (metres) |
| `--z-scale FLOAT` | `1.5` | Vertical exaggeration factor |
| `--target-size FLOAT` | *none* | Rescale longest XY dimension to this mm value |
| `--output PATH` | `hole.stl` | Output file (`.stl` or `.obj`) |

### `generate-all` options

All of the above plus:

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

# Run
python -m src.main generate \
    --dtm data/terrain.tif \
    --hole-id 123456789 \
    --output output/hole.stl
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
│   ├── main.py            # Click CLI
│   ├── dtm_processor.py   # GeoTIFF loading & clipping
│   ├── course_fetcher.py  # OpenStreetMap Overpass queries
│   ├── mesh_generator.py  # Elevation → watertight 3-D mesh
│   └── exporter.py        # STL / OBJ export
├── tests/
│   ├── test_dtm_processor.py
│   ├── test_mesh_generator.py
│   ├── test_course_fetcher.py
│   └── test_exporter.py
├── data/      # Place your DTM GeoTIFFs here (not committed)
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

1. **DTM Processor** (`src/dtm_processor.py`)  
   Opens a GeoTIFF with `rasterio`, reprojects the hole geometry into the
   raster's CRS, and returns a clipped NumPy elevation array.

2. **Course Fetcher** (`src/course_fetcher.py`)  
   Queries the OpenStreetMap Overpass API for `golf=hole` ways tagged
   `par=3`.  Returns Shapely polygons in WGS-84.

3. **Mesh Generator** (`src/mesh_generator.py`)  
   Converts the elevation grid to a watertight trimesh solid:
   - Surface: two triangles per grid cell
   - Side walls: perimeter extruded to a flat base plane
   - Bottom cap: fan triangulation
   - Optional vertical exaggeration and print-bed rescaling

4. **Exporter** (`src/exporter.py`)  
   Writes the mesh to STL (default) or OBJ using `trimesh`.

---

## License

MIT – see [LICENSE](LICENSE).
