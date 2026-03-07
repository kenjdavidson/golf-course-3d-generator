# ---------------------------------------------------------------------------
# Golf Course 3D Generator – Dockerfile
# ---------------------------------------------------------------------------
# Multi-stage build:
#   1. builder – install Python dependencies in an isolated layer
#   2. runtime – lean production image
# ---------------------------------------------------------------------------

# ---- builder ---------------------------------------------------------------
FROM python:3.11-slim AS builder

# System libraries required to compile GDAL / rasterio wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gdal-bin \
        libgdal-dev \
        libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies into a prefix so they can be copied cleanly
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# ---- runtime ---------------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal32 \
        libspatialindex6 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy source code
COPY src/ ./src/

# Mount points that users are expected to bind-mount:
#   /data   – place your GeoTIFF DTM/DEM files here (read-only is fine)
#   /output – generated STL / OBJ files are written here
VOLUME /data
VOLUME /output

# Default entrypoint – users supply the sub-command and flags
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]
