"""
Tests for the generators package.

Covers:
* HoleGenerator abstract interface via concrete sub-class.
* VRTHoleGenerator (acquire_elevation mocked, build_meshes verified).
* ImageServerHoleGenerator (HTTP and DTMProcessor mocked).
* create_generator factory function.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from unittest.mock import MagicMock, patch, PropertyMock

from src.generators.base import HoleGenerator
from src.generators.vrt_generator import VRTHoleGenerator
from src.generators.imageserver_generator import ImageServerHoleGenerator
from src.generators.factory import create_generator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_geotiff(
    elevation: np.ndarray | None = None,
    west: float = -79.89,
    south: float = 43.50,
    east: float = -79.87,
    north: float = 43.52,
    crs: str = "EPSG:4326",
) -> str:
    """Write a small GeoTIFF to a temp file and return its path."""
    if elevation is None:
        elevation = np.ones((16, 16), dtype=np.float32) * 100.0
    rows, cols = elevation.shape
    transform = from_bounds(west, south, east, north, cols, rows)

    fd, path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=rows, width=cols, count=1, dtype=elevation.dtype,
        crs=crs, transform=transform,
    ) as ds:
        ds.write(elevation, 1)
    return path


def _flat_transform():
    return rasterio.transform.from_bounds(0.0, 0.0, 1.0, 1.0, 20, 20)


def _terrain_elevation():
    z = np.ones((20, 20), dtype=np.float64) * 50.0
    z[8:12, 8:12] = 65.0   # central plateau
    z[0:3, 0:3] = 30.0     # corner depression
    return z


# ---------------------------------------------------------------------------
# HoleGenerator base class
# ---------------------------------------------------------------------------

class ConcreteGenerator(HoleGenerator):
    """Minimal concrete implementation for testing the base class."""

    def acquire_elevation(self, lat, lon, buffer_m, geometry=None, label=""):
        elevation = _terrain_elevation()
        transform = _flat_transform()
        return elevation, transform

    def build_meshes(self, elevation, transform):
        gen = self._make_mesh_generator()
        return gen.generate_layers(elevation, transform)


class TestHoleGeneratorBase:
    def test_generate_creates_output_directory(self):
        gen = ConcreteGenerator(base_thickness=1.0)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "hole_out")
            gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path=out, label="test")
            assert os.path.isdir(out)

    def test_generate_produces_three_stl_files(self):
        gen = ConcreteGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers")
            gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path=out)
            stls = [f for f in os.listdir(out) if f.endswith(".stl")]
            assert len(stls) == 3

    def test_generate_produces_zip_when_path_ends_in_zip(self):
        gen = ConcreteGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers.zip")
            gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path=out)
            assert os.path.isfile(out)

    def test_make_mesh_generator_uses_settings(self):
        gen = ConcreteGenerator(base_thickness=5.0, z_scale=3.0, target_size_mm=200.0)
        mg = gen._make_mesh_generator()
        assert mg.base_thickness == 5.0
        assert mg.z_scale == 3.0
        assert mg.target_size_mm == 200.0


# ---------------------------------------------------------------------------
# VRTHoleGenerator
# ---------------------------------------------------------------------------

class TestVRTHoleGenerator:
    def test_acquire_elevation_uses_dtm_processor(self):
        """VRTHoleGenerator should open the VRT and return an elevation array."""
        path = _make_geotiff()
        try:
            with (
                patch("src.generators.vrt_generator.VRTBuilder") as MockVRT,
                patch("src.generators.vrt_generator.DTMProcessor") as MockDTM,
            ):
                MockVRT.return_value.ensure_vrt.return_value = path
                mock_proc = MagicMock()
                mock_proc.__enter__ = MagicMock(return_value=mock_proc)
                mock_proc.__exit__ = MagicMock(return_value=False)
                mock_proc.clip_to_geometry.return_value = (
                    np.ones((10, 10)), _flat_transform()
                )
                MockDTM.return_value = mock_proc

                gen = VRTHoleGenerator(dtm_dir="/fake/dir")
                elevation, transform = gen.acquire_elevation(
                    lat=43.5, lon=-79.8, buffer_m=50, label="test"
                )

            assert isinstance(elevation, np.ndarray)
        finally:
            os.unlink(path)

    def test_build_meshes_returns_three_keys(self):
        elevation = _terrain_elevation()
        transform = _flat_transform()
        with tempfile.TemporaryDirectory() as tmp:
            gen = VRTHoleGenerator(dtm_dir=tmp)
            # Stub out acquire_elevation to bypass file I/O
            meshes = gen.build_meshes(elevation, transform)
        assert set(meshes.keys()) == {"base_terrain", "green_inlay", "bunker_cutout"}

    def test_generate_with_geometry_calls_clip(self):
        """When a hole geometry is supplied it should be used for clipping."""
        from shapely.geometry import box

        path = _make_geotiff()
        try:
            with (
                patch("src.generators.vrt_generator.VRTBuilder") as MockVRT,
                patch("src.generators.vrt_generator.DTMProcessor") as MockDTM,
            ):
                MockVRT.return_value.ensure_vrt.return_value = path
                mock_proc = MagicMock()
                mock_proc.__enter__ = MagicMock(return_value=mock_proc)
                mock_proc.__exit__ = MagicMock(return_value=False)
                mock_proc.clip_to_geometry.return_value = (
                    np.ones((10, 10)), _flat_transform()
                )
                MockDTM.return_value = mock_proc

                geom = box(-79.89, 43.50, -79.87, 43.52)
                gen = VRTHoleGenerator(dtm_dir="/fake/dir")
                gen.acquire_elevation(lat=43.5, lon=-79.8, buffer_m=50, geometry=geom)

            mock_proc.clip_to_geometry.assert_called_once()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# ImageServerHoleGenerator
# ---------------------------------------------------------------------------

def _make_tiff_bytes() -> bytes:
    path = _make_geotiff(
        elevation=np.ones((16, 16), dtype=np.float32) * 80.0,
        west=-8_890_000.0, south=5_450_000.0,
        east=-8_890_000.0 + 300.0, north=5_450_000.0 + 300.0,
        crs="EPSG:3857",
    )
    with open(path, "rb") as fh:
        data = fh.read()
    os.unlink(path)
    return data


class TestImageServerHoleGenerator:
    def _mock_response(self):
        resp = MagicMock()
        resp.content = _make_tiff_bytes()
        resp.raise_for_status = MagicMock()
        return resp

    def test_acquire_elevation_fetches_tiff(self):
        with patch("src.services.ontario_geohub.requests.get", return_value=self._mock_response()):
            gen = ImageServerHoleGenerator()
            elevation, transform = gen.acquire_elevation(lat=43.5, lon=-79.8, buffer_m=150)
        assert isinstance(elevation, np.ndarray)
        assert elevation.ndim == 2

    def test_acquire_elevation_deletes_temp_file(self):
        """Temp GeoTIFF must be removed after acquisition."""
        created: list[str] = []

        def patched_fetch(lat, lon, buffer_m):
            path = _make_geotiff()
            created.append(path)
            return path

        with patch("src.services.ontario_geohub.requests.get", return_value=self._mock_response()):
            gen = ImageServerHoleGenerator()
            gen._client.fetch_elevation_tiff = patched_fetch
            gen.acquire_elevation(lat=43.5, lon=-79.8, buffer_m=150)

        for p in created:
            assert not os.path.exists(p), f"Temp file was not cleaned up: {p}"

    def test_build_meshes_returns_three_keys(self):
        elevation = _terrain_elevation()
        transform = _flat_transform()
        gen = ImageServerHoleGenerator()
        meshes = gen.build_meshes(elevation, transform)
        assert set(meshes.keys()) == {"base_terrain", "green_inlay", "bunker_cutout"}

    def test_build_meshes_all_trimesh_instances(self):
        import trimesh
        elevation = _terrain_elevation()
        transform = _flat_transform()
        gen = ImageServerHoleGenerator()
        meshes = gen.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert isinstance(mesh, trimesh.Trimesh), f"{name} is not a Trimesh"


# ---------------------------------------------------------------------------
# create_generator factory
# ---------------------------------------------------------------------------

class TestCreateGenerator:
    def test_returns_vrt_generator_when_dtm_dir_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen = create_generator(dtm_dir=tmp)
        assert isinstance(gen, VRTHoleGenerator)

    def test_returns_imageserver_generator_when_no_dtm_dir(self):
        gen = create_generator()
        assert isinstance(gen, ImageServerHoleGenerator)

    def test_vrt_generator_has_correct_dtm_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen = create_generator(dtm_dir=tmp)
            assert gen.dtm_dir == tmp

    def test_generator_settings_propagated(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen = create_generator(
                dtm_dir=tmp,
                base_thickness=5.0,
                z_scale=2.0,
                target_size_mm=150.0,
            )
        assert gen.base_thickness == 5.0
        assert gen.z_scale == 2.0
        assert gen.target_size_mm == 150.0

    def test_imageserver_generator_settings_propagated(self):
        gen = create_generator(base_thickness=4.0, z_scale=1.0)
        assert gen.base_thickness == 4.0
        assert gen.z_scale == 1.0
