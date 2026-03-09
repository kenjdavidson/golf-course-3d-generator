# golf-course-3d-generator

> Automate the generation of 3D-printable par-3 golf hole models from
> publicly available Digital Terrain Model (DTM) data.

---

## Overview

This Docker-based tool takes either a **directory of local DTM tile files**
or fetches elevation automatically from the **Ontario ArcGIS ImageServer**,
combines it with golf hole geometry from **OpenStreetMap**, and produces
three watertight **STL** meshes ready for multi-material 3D printing.
The intended output is a commemorative *Hole in One* plaque or desk ornament
that captures the real terrain of a par-3 hole.

```
LOCAL PATH  (generate / generate-all):
DTM tiles ─► VRT index ─┐
                          ├──► clip ──► GradientMeshProcessor ──► LayeredSTLOutput ──► STL × 3
OSM hole data ────────────┘

CLOUD-NATIVE PATH  (generate-api):
Ontario ArcGIS ImageServer ──► GeoTIFF ──► LoGMeshProcessor ──► LayeredSTLOutput ──► STL × 3
```

### Key features

| Feature | Detail |
|---------|--------|
| Input (local) | Directory of DTM tile files (`.img`, `.tif`, etc.) |
| Input (cloud) | Ontario ArcGIS ImageServer (automatic, no local files needed) |
| Output format | STL (three layer files) |
| Multi-tile indexing | `index.vrt` built automatically with `gdalbuildvrt` |
| Coordinate crop | `--lat` / `--lon` selects a study area |
| Golf course data | OpenStreetMap Overpass API (automatic, optional on cloud path) |
| Feature extraction | scikit-image / SciPy blob detection for greens & bunkers |
| Layered output | Three STLs for multi-material / filament-swap printing |
| Vertical exaggeration | Configurable `--z-scale` |
| Print-bed sizing | `--target-size` rescales to a given mm dimension |
| Solid base | Configurable `--base-thickness` for a printable solid |
| Docker | Fully containerised; no local Python setup needed |

---

## Quick start (Docker)

### Option A – Local DTM tiles (`generate` / `generate-all`)

#### 1. Obtain DTM tile files

Download a package of elevation tiles covering your golf course, e.g.

- **USGS 3DEP** – <https://apps.nationalmap.gov/downloader/>
- **Copernicus DEM** – <https://spacedata.copernicus.eu/>
- **OpenTopography** – <https://opentopography.org/>
- **Natural Resources Canada (GeoGratis)** – <https://maps.canada.ca/czs/index-en.html>
  Select *Digital Elevation* → *CDEM* (Canadian DEM, 20 m) or *HRDEM* (High-Resolution DEM, 1 m where available).
- **Ontario GeoHub (LiDAR-derived DEM)** – <https://geohub.lio.gov.on.ca/>
  Search for *"Digital Elevation Model"* or *"LiDAR"*; Ontario Ministry of Natural Resources provides
  0.5 m – 1 m resolution tiles for most of the province (e.g. the Milton Package with 249 `.img` files).

Place the tile files in a subdirectory of `data/`:

```
data/
└── milton/
    ├── tile_001.img
    ├── tile_002.img
    └── …  (249 tiles)
```

An `index.vrt` is created automatically in the same directory the first time
you run the tool.  If the directory contains only a single tile file that is
fine too — the VRT simply wraps that one tile.

#### 2. Find the OSM way ID (optional)

1. Go to <https://www.openstreetmap.org/> and navigate to your golf course.
2. Click the *Query features* tool and click on the par-3 hole outline.
3. Note the **Way ID** (e.g. `123456789`).

When `--hole-id` is supplied the OSM outline clips the raster to the exact
hole boundary.  When omitted, the `--lat`/`--lon` + `--buffer` bounding box
is used and features (greens, bunkers) are detected automatically from the
elevation data using a Laplacian of Gaussian (LoG) filter.

#### 3. Build and run

```bash
# Build the image (first time only)
docker compose build

# Generate a single par-3 hole (3 STL layers) – with OSM hole outline
docker compose run --rm generator generate \
    --dtm-dir /data/milton \
    --hole-id 123456789 \
    --lat 43.5123 --lon -79.8765 \
    --output /output/hole3_layers

# Generate a single par-3 hole – automatic feature detection (no --hole-id)
docker compose run --rm generator generate \
    --dtm-dir /data/milton \
    --lat 43.5123 --lon -79.8765 \
    --buffer 150 \
    --output /output/hole3_layers
```

#### 4. Generate all par-3 holes near a coordinate

```bash
docker compose run --rm generator generate-all \
    --dtm-dir /data/milton \
    --lat 43.5123 --lon -79.8765 \
    --radius 3000 \
    --output-dir /output
```

Each hole found produces a subdirectory (e.g. `hole-3/`) containing its
three STL files.

### Option B – Cloud-native path (`generate-api`)

No local files required.  Elevation data is fetched automatically from the
[Ontario DTM LiDAR-Derived ImageServer](https://ws.geoservices.lrc.gov.on.ca/arcgis5/rest/services/Elevation/Ontario_DTM_LidarDerived/ImageServer).
Feature segmentation (greens/tees and bunkers) is performed automatically
using a Laplacian of Gaussian (LoG) filter when no OSM hole outline is
provided.

```bash
# Fully automatic – lat/lon only, features detected via LoG
docker compose run --rm generator generate-api \
    --lat 43.5123 --lon -79.8765 \
    --buffer 150 \
    --output /output/hole3_layers

# With optional OSM hole outline for exact boundary clipping
docker compose run --rm generator generate-api \
    --hole-id 123456789 \
    --lat 43.5123 --lon -79.8765 \
    --output /output/hole3_layers
```

The output directory contains:

| File | 3D Print purpose |
|------|-----------------|
| `base_terrain.stl` | Main structural body |
| `green_inlay.stl` | Green / tee colour insert |
| `bunker_cutout.stl` | Sand / bunker filament inlay |

Import all three into Bambu Studio or PrusaSlicer as a **multi-part object**
and assign a different filament to each part.

Pass `--output /output/hole3_layers.zip` to receive a single ZIP archive
instead of a directory.

---

## CLI reference

```
Usage: python -m src.main [OPTIONS] COMMAND [ARGS]...

  Automate generation of 3D-printable par-3 golf hole models from DTM data.

Commands:
  generate      Generate a 3D model for a single par-3 hole from local DTM files.
  generate-all  Find all par-3 holes near LAT/LON and generate a model for each (local DTM).
  generate-api  Generate a 3D model by fetching elevation from the Ontario ArcGIS ImageServer.
```

### `generate` options

| Option | Default | Description |
|--------|---------|-------------|
| `--dtm-dir PATH` | *required* | Directory of DTM tile files; `index.vrt` built automatically |
| `--lat FLOAT` | *required* | Latitude of study-area centre (WGS-84) |
| `--lon FLOAT` | *required* | Longitude of study-area centre (WGS-84) |
| `--hole-id INT` | *none* | OpenStreetMap way ID (`golf=hole`); when omitted, features are detected automatically via LoG |
| `--buffer FLOAT` | `50` | Buffer in metres added around the hole boundary before clipping |
| `--base-thickness FLOAT` | `3.0` | Solid base thickness (metres) |
| `--z-scale FLOAT` | `1.5` | Vertical exaggeration factor |
| `--target-size FLOAT` | *none* | Rescale longest XY dimension to this mm value |
| `--output PATH` | `hole_layers` | Output directory or `.zip` path for the three layer STLs |

### `generate-all` options

| Option | Default | Description |
|--------|---------|-------------|
| `--dtm-dir PATH` | *required* | Directory of DTM tile files; `index.vrt` built automatically |
| `--lat FLOAT` | *required* | Latitude of search centre (WGS-84) |
| `--lon FLOAT` | *required* | Longitude of search centre (WGS-84) |
| `--radius FLOAT` | `5000` | Search radius in metres |
| `--buffer FLOAT` | `50` | Buffer in metres added around each hole boundary before clipping |
| `--base-thickness FLOAT` | `3.0` | Solid base thickness (metres) |
| `--z-scale FLOAT` | `1.5` | Vertical exaggeration factor |
| `--target-size FLOAT` | *none* | Rescale longest XY dimension to this mm value |
| `--output-dir PATH` | `output` | Parent directory; each hole gets its own subdirectory |

### `generate-api` options

| Option | Default | Description |
|--------|---------|-------------|
| `--lat FLOAT` | *required* | Latitude of study-area centre (WGS-84) |
| `--lon FLOAT` | *required* | Longitude of study-area centre (WGS-84) |
| `--hole-id INT` | *none* | OpenStreetMap way ID (`golf=hole`); when omitted, features are detected automatically via LoG |
| `--buffer FLOAT` | `150` | Half-width of the square bounding box (metres) fetched from the ImageServer |
| `--base-thickness FLOAT` | `3.0` | Solid base thickness (metres) |
| `--z-scale FLOAT` | `1.5` | Vertical exaggeration factor |
| `--target-size FLOAT` | *none* | Rescale longest XY dimension to this mm value |
| `--output PATH` | `hole_layers` | Output directory or `.zip` path for the three layer STLs |

---

## Running without Docker

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt-get install gdal-bin libgdal-dev libspatialindex-dev

# Install Python dependencies
pip install -r requirements.txt

# Generate a single hole – local VRT path, with OSM hole outline
python -m src.main generate \
    --dtm-dir data/milton \
    --hole-id 123456789 \
    --lat 43.5123 --lon -79.8765 \
    --output output/hole_layers

# Generate a single hole – local VRT path, automatic feature detection
python -m src.main generate \
    --dtm-dir data/milton \
    --lat 43.5123 --lon -79.8765 \
    --buffer 150 \
    --output output/hole_layers

# Generate a single hole – cloud-native path (Ontario ImageServer, no local files)
python -m src.main generate-api \
    --lat 43.5123 --lon -79.8765 \
    --buffer 150 \
    --output output/hole_layers

# Generate all par-3 holes near a coordinate – local VRT path
python -m src.main generate-all \
    --dtm-dir data/milton \
    --lat 43.5123 --lon -79.8765 \
    --radius 5000 \
    --output-dir output
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
│   ├── main.py             # Click CLI entry point (registers sub-commands)
│   ├── pipeline.py         # Backward-compat shim; delegates to generators/
│   ├── geo_utils.py        # Shared geographic utilities (UTM buffer, study-area)
│   ├── dtm_processor.py    # VRT / GeoTIFF loading & clipping
│   ├── vrt_builder.py      # Multi-tile VRT index builder (gdalbuildvrt)
│   ├── course_fetcher.py   # OpenStreetMap Overpass queries
│   ├── mesh_generator.py   # Elevation → watertight 3-D mesh (+ layer support)
│   ├── exporter.py         # STL / ZIP export (low-level I/O helpers)
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── options.py       # Shared Click option decorators
│   │   ├── generate.py      # `generate` sub-command (local DTM)
│   │   ├── generate_all.py  # `generate-all` sub-command (local DTM, batch)
│   │   └── generate_api.py  # `generate-api` sub-command (Ontario ImageServer)
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── base.py          # HoleGenerator abstract base class (acquire_elevation only)
│   │   ├── factory.py       # create_generator() factory function
│   │   ├── vrt_generator.py         # VRTHoleGenerator (local DTM path)
│   │   └── imageserver_generator.py # ImageServerHoleGenerator (cloud path)
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── base.py                  # MeshProcessor abstract base class
│   │   ├── gradient_processor.py    # GradientMeshProcessor (gradient/threshold)
│   │   └── log_processor.py         # LoGMeshProcessor (Laplacian of Gaussian)
│   ├── outputs/
│   │   ├── __init__.py
│   │   ├── base.py                  # OutputWriter abstract base class
│   │   └── layered_stl_output.py    # LayeredSTLOutput (STL files / ZIP archive)
│   └── services/
│       ├── __init__.py
│       ├── ontario_geohub.py    # Ontario ArcGIS ImageServer REST client
│       └── feature_extractor.py # skimage/scipy green & bunker detection
├── tests/
│   ├── test_dtm_processor.py
│   ├── test_mesh_generator.py
│   ├── test_mesh_generator_layers.py
│   ├── test_vrt_builder.py
│   ├── test_course_fetcher.py
│   ├── test_exporter.py
│   ├── test_ontario_geohub.py
│   ├── test_feature_extractor.py
│   ├── test_generators.py
│   ├── test_processors.py
│   ├── test_outputs.py
│   ├── test_generate_command.py
│   └── test_generate_api_command.py
├── data/      # Place your DTM tile directories here (not committed)
└── output/    # Generated STL files (not committed)
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

The generation logic is organised as a three-stage pipeline:

```
DataSource (HoleGenerator.acquire_elevation)
    │
    ▼
MeshProcessor (MeshProcessor.build_meshes)
    │
    ▼
OutputWriter (OutputWriter.write)
```

Each stage is independently abstracted and can be swapped without modifying
the others.  Concrete implementations are selected via the
`src.generators.factory.create_generator()` factory (or by instantiating
generators directly).

### Stage 1 – Data acquisition (`generators/`)

A :class:`HoleGenerator` sub-class implements `acquire_elevation()` to
obtain a NumPy elevation array and its rasterio affine transform:

| Class | Source |
|-------|--------|
| `VRTHoleGenerator` | Local DTM tile directory → GDAL VRT index |
| `ImageServerHoleGenerator` | Ontario ArcGIS ImageServer (cloud, no local files) |

### Local DTM path (`generate` / `generate-all`)

1. **VRT Builder** (`src/vrt_builder.py`)
   Scans the tile directory for `.img` (or `.tif`) files and runs
   `gdalbuildvrt -overwrite` to create `index.vrt`.  An existing VRT is
   reused on subsequent runs without rebuilding.

2. **Course Fetcher** (`src/course_fetcher.py`)
   When `--hole-id` is supplied, queries the OpenStreetMap Overpass API for
   the `golf=hole` way.  Returns a Shapely polygon in WGS-84.  When omitted,
   the study area is derived from `--lat`/`--lon` + `--buffer`.

3. **VRT Generator** (`src/generators/vrt_generator.py`)
   Implements `HoleGenerator.acquire_elevation` for the local DTM path:
   opens the VRT with `rasterio`, reprojects the hole geometry into the
   raster's CRS, and returns a clipped NumPy elevation array.

### Cloud-native path (`generate-api`)

1. **Ontario GeoHub Client** (`src/services/ontario_geohub.py`)
   Sends an `exportImage` REST request to the Ontario DTM LiDAR-Derived
   ImageServer with a bounding box derived from `--lat` / `--lon` and
   `--buffer`.  Returns a 32-bit float GeoTIFF in EPSG:3857 stored in a
   temporary file.

2. **ImageServer Generator** (`src/generators/imageserver_generator.py`)
   Implements `HoleGenerator.acquire_elevation` for the cloud path: fetches
   the GeoTIFF via the Ontario GeoHub Client, opens it with `rasterio`, and
   returns the elevation array.

---

### Stage 2 – Mesh processing (`processors/`)

A :class:`MeshProcessor` sub-class implements `build_meshes()` to convert
the elevation array into a ``name → Trimesh`` dictionary.  Different
processors apply different feature-detection and layer-construction strategies:

| Class | Algorithm |
|-------|-----------|
| `GradientMeshProcessor` | Gradient-magnitude thresholding (default for VRT path) |
| `LoGMeshProcessor` | Laplacian of Gaussian feature extraction (default for cloud path) |

Processors are **fully decoupled** from the data source — any processor can
be used with any generator by passing it at construction time::

    from src.generators.factory import create_generator
    from src.processors.log_processor import LoGMeshProcessor

    gen = create_generator(
        dtm_dir="/data/milton",
        processor=LoGMeshProcessor(z_scale=2.0),
    )

#### `GradientMeshProcessor` (`src/processors/gradient_processor.py`)

Identifies features by thresholding the elevation (Z) values relative to the
median terrain height and the local slope:

- *green inlay*: low gradient magnitude **and** elevation ≥ median.
- *bunker*: below ``median − 0.5 × std``.

Delegates triangulation to `MeshGenerator.generate_layers()`.

#### `LoGMeshProcessor` (`src/processors/log_processor.py`)

Uses :class:`~src.services.feature_extractor.FeatureExtractor` to detect
features directly from raw elevation data:

- *green inlay*: contiguous flat plateaus at or above median elevation,
  detected via gradient-magnitude thresholding and `skimage.measure.label`.
- *bunker*: local depressions revealed by a morphological bottom-hat
  transform (`scipy.ndimage.grey_closing` − original), filtered to pixels
  below `median − 0.5 × std`.

---

### Stage 3 – Output writing (`outputs/`)

An :class:`OutputWriter` sub-class implements `write()` to persist the
``name → Trimesh`` mapping in the desired format:

| Class | Output |
|-------|--------|
| `LayeredSTLOutput` | Three `.stl` files in a directory, or a single `.zip` archive |

Custom writers can be injected to support new output styles (e.g. exact
DTM height maps, carved in-ground plaques) without modifying the acquisition
or processing stages::

    from src.outputs.base import OutputWriter

    class MyCustomOutput(OutputWriter):
        def write(self, meshes, output_path):
            # custom serialisation logic here
            ...

    gen = create_generator(output_writer=MyCustomOutput())

---

### Generator architecture

```
HoleGenerator (abstract, src/generators/base.py)
├── acquire_elevation()   ← implemented by each sub-class (data source)
├── generate()            ← orchestrates acquire → process → write
│       │
│       ├── MeshProcessor.build_meshes()   ← injected or default per sub-class
│       └── OutputWriter.write()           ← injected or LayeredSTLOutput default
│
├── VRTHoleGenerator          (local DTM / VRT)
│   └── default processor: GradientMeshProcessor
└── ImageServerHoleGenerator  (Ontario ArcGIS ImageServer)
    └── default processor: LoGMeshProcessor

MeshProcessor (abstract, src/processors/base.py)
├── GradientMeshProcessor  (gradient/threshold)
└── LoGMeshProcessor       (Laplacian of Gaussian)

OutputWriter (abstract, src/outputs/base.py)
└── LayeredSTLOutput       (three STLs or one ZIP)
```

Use `src.generators.factory.create_generator()` to select the right
implementation programmatically (pass `dtm_dir` for local, omit for cloud).
Custom processors and output writers can be injected via the `processor` and
`output_writer` parameters.

---

## License

MIT – see [LICENSE](LICENSE).
