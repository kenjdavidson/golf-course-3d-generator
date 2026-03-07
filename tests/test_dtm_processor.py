"""
Tests for DTMProcessor.

Uses in-memory GeoTIFF fixtures created with rasterio so no external
files are required.
"""

from __future__ import annotations

import io
import os
import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box

from src.dtm_processor import DTMProcessor


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_geotiff(
    elevation: np.ndarray,
    west: float = -74.01,
    south: float = 40.70,
    east: float = -74.00,
    north: float = 40.71,
    nodata: float = -9999.0,
) -> str:
    """Write a small GeoTIFF to a temp file and return its path."""
    rows, cols = elevation.shape
    transform = from_bounds(west, south, east, north, cols, rows)

    fd, path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype=elevation.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as ds:
        ds.write(elevation, 1)

    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDTMProcessorOpenClose:
    def test_open_valid_file(self):
        elevation = np.arange(100, dtype=np.float32).reshape(10, 10)
        path = _make_geotiff(elevation)
        try:
            proc = DTMProcessor(path)
            proc.open()
            assert proc.crs is not None
            proc.close()
        finally:
            os.unlink(path)

    def test_context_manager(self):
        elevation = np.arange(100, dtype=np.float32).reshape(10, 10)
        path = _make_geotiff(elevation)
        try:
            with DTMProcessor(path) as proc:
                assert proc.crs is not None
            # After exiting the dataset should be closed (no _dataset)
            assert proc._dataset is None
        finally:
            os.unlink(path)

    def test_requires_open_before_crs(self):
        proc = DTMProcessor("nonexistent.tif")
        with pytest.raises(RuntimeError, match="not open"):
            _ = proc.crs

    def test_requires_open_before_bounds(self):
        proc = DTMProcessor("nonexistent.tif")
        with pytest.raises(RuntimeError, match="not open"):
            _ = proc.bounds


class TestDTMProcessorClip:
    def test_clip_to_geometry_returns_array_and_transform(self):
        elevation = np.ones((20, 20), dtype=np.float32) * 100.0
        path = _make_geotiff(elevation)
        try:
            with DTMProcessor(path) as proc:
                geom = box(-74.005, 40.701, -74.001, 40.709)
                arr, transform = proc.clip_to_geometry(geom)
            assert isinstance(arr, np.ndarray)
            assert arr.ndim == 2
            assert arr.shape[0] > 0
            assert arr.shape[1] > 0
        finally:
            os.unlink(path)

    def test_clip_to_bounds_matches_geometry_clip(self):
        elevation = np.random.rand(30, 30).astype(np.float32) * 50
        path = _make_geotiff(elevation)
        try:
            with DTMProcessor(path) as proc:
                bounds = (-74.005, 40.701, -74.001, 40.709)
                arr1, _ = proc.clip_to_bounds(bounds)
                geom = box(*bounds)
                arr2, _ = proc.clip_to_geometry(geom)
            assert arr1.shape == arr2.shape
            np.testing.assert_array_almost_equal(arr1, arr2)
        finally:
            os.unlink(path)

    def test_nodata_replaced_with_nan(self):
        elevation = np.ones((10, 10), dtype=np.float32) * 50.0
        elevation[5, 5] = -9999.0  # nodata sentinel
        path = _make_geotiff(elevation, nodata=-9999.0)
        try:
            with DTMProcessor(path) as proc:
                geom = box(-74.009, 40.701, -74.001, 40.709)
                arr, _ = proc.clip_to_geometry(geom)
            assert np.any(np.isnan(arr))
        finally:
            os.unlink(path)


class TestDTMProcessorProperties:
    def test_resolution_returns_tuple(self):
        elevation = np.ones((10, 10), dtype=np.float32)
        path = _make_geotiff(elevation)
        try:
            with DTMProcessor(path) as proc:
                res = proc.resolution
            assert len(res) == 2
            assert all(r > 0 for r in res)
        finally:
            os.unlink(path)

    def test_bounds_contains_expected_coordinates(self):
        elevation = np.ones((10, 10), dtype=np.float32)
        path = _make_geotiff(elevation, west=-74.01, south=40.70, east=-74.00, north=40.71)
        try:
            with DTMProcessor(path) as proc:
                b = proc.bounds
            assert b.left < b.right
            assert b.bottom < b.top
        finally:
            os.unlink(path)
