"""
Tests for VRTBuilder.

Uses temporary directories and synthetic ``.tif`` files so no external
GDAL datasets are required for most tests.  Tests that invoke
``gdalbuildvrt`` are marked to skip gracefully when the binary is absent.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from src.vrt_builder import VRTBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_test_raster(path: str, rows: int = 5, cols: int = 5) -> None:
    """Write a minimal GeoTIFF raster file at *path*."""
    transform = from_bounds(0.0, 0.0, 1.0, 1.0, cols, rows)
    data = np.arange(rows * cols, dtype=np.float32).reshape(rows, cols)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as ds:
        ds.write(data, 1)


def _gdalbuildvrt_available() -> bool:
    """Return True if ``gdalbuildvrt`` is on the PATH."""
    try:
        result = subprocess.run(
            ["gdalbuildvrt", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


requires_gdalbuildvrt = pytest.mark.skipif(
    not _gdalbuildvrt_available(),
    reason="gdalbuildvrt not available on this system",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVRTBuilderInit:
    def test_init_stores_abs_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = VRTBuilder(tmp)
            assert os.path.isabs(builder.data_dir)

    def test_init_default_vrt_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = VRTBuilder(tmp)
            assert builder.vrt_path.endswith("index.vrt")

    def test_init_custom_vrt_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = VRTBuilder(tmp, vrt_filename="mosaic.vrt")
            assert builder.vrt_path.endswith("mosaic.vrt")

    def test_init_missing_dir_raises(self):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            VRTBuilder("/nonexistent/path/xyz")

    def test_default_tile_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = VRTBuilder(tmp)
            assert builder.tile_pattern == "*.img"


class TestVRTBuilderEnsureVRTReuse:
    def test_reuses_existing_vrt(self):
        """ensure_vrt() returns immediately when index.vrt already exists."""
        with tempfile.TemporaryDirectory() as tmp:
            vrt_path = os.path.join(tmp, "index.vrt")
            # Create a dummy file to simulate a pre-existing VRT.
            with open(vrt_path, "w") as fh:
                fh.write("<VRTDataset/>")
            builder = VRTBuilder(tmp)
            result = builder.ensure_vrt()
            assert result == vrt_path

    def test_raises_when_no_tiles_found(self):
        """ensure_vrt() raises FileNotFoundError when no tiles match pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            builder = VRTBuilder(tmp, tile_pattern="*.img")
            with pytest.raises(FileNotFoundError, match="No tiles matching"):
                builder.ensure_vrt()


class TestVRTBuilderRunGdalbuildvrt:
    @requires_gdalbuildvrt
    def test_builds_vrt_from_tif_tiles(self):
        """gdalbuildvrt is called and produces a readable VRT."""
        with tempfile.TemporaryDirectory() as tmp:
            # Write two small GeoTIFF tiles with .tif extension.
            tile1 = os.path.join(tmp, "tile1.tif")
            tile2 = os.path.join(tmp, "tile2.tif")
            _write_test_raster(tile1)
            _write_test_raster(tile2)

            builder = VRTBuilder(tmp, tile_pattern="*.tif")
            vrt_path = builder.ensure_vrt()

            assert os.path.exists(vrt_path)
            # rasterio should be able to open the resulting VRT.
            with rasterio.open(vrt_path) as ds:
                assert ds.count >= 1

    @requires_gdalbuildvrt
    def test_vrt_path_returned(self):
        """ensure_vrt() returns the absolute path of the created VRT."""
        with tempfile.TemporaryDirectory() as tmp:
            tile = os.path.join(tmp, "tile.tif")
            _write_test_raster(tile)
            builder = VRTBuilder(tmp, tile_pattern="*.tif")
            vrt_path = builder.ensure_vrt()
            assert os.path.isabs(vrt_path)
            assert vrt_path.endswith("index.vrt")

    def test_run_gdalbuildvrt_raises_on_failure(self, monkeypatch):
        """_run_gdalbuildvrt raises RuntimeError when the subprocess fails."""
        import subprocess as _subprocess

        def _fake_run(cmd, capture_output, text):
            class _Result:
                returncode = 1
                stderr = "simulated error"
            return _Result()

        monkeypatch.setattr(_subprocess, "run", _fake_run)

        with tempfile.TemporaryDirectory() as tmp:
            builder = VRTBuilder(tmp)
            with pytest.raises(RuntimeError, match="gdalbuildvrt failed"):
                builder._run_gdalbuildvrt(["/fake/tile.img"])
