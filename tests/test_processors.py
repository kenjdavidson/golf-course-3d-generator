"""
Tests for the processors package.

Covers:
* MeshProcessor abstract interface via concrete sub-class.
* GradientMeshProcessor – three layer meshes via gradient/threshold.
* LoGMeshProcessor – three layer meshes via LoG feature extraction.
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio.transform
import trimesh

from src.processors.base import MeshProcessor
from src.processors.gradient_processor import GradientMeshProcessor
from src.processors.log_processor import LoGMeshProcessor
from src.mesh_generator import MeshGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_transform(rows: int = 20, cols: int = 20) -> rasterio.transform.Affine:
    return rasterio.transform.from_bounds(0.0, 0.0, 1.0, 1.0, cols, rows)


def _terrain_elevation(rows: int = 20, cols: int = 20) -> np.ndarray:
    z = np.ones((rows, cols), dtype=np.float64) * 50.0
    z[8:12, 8:12] = 65.0   # central plateau → green candidate
    z[0:3, 0:3] = 30.0     # corner depression → bunker candidate
    return z


# ---------------------------------------------------------------------------
# MeshProcessor abstract interface
# ---------------------------------------------------------------------------

class ConcreteMeshProcessor(MeshProcessor):
    """Minimal concrete implementation for testing the base class."""

    def build_meshes(self, elevation, transform):
        gen = self._make_mesh_generator()
        return {"base_terrain": gen.generate(elevation, transform)}


class TestMeshProcessorBase:
    def test_make_mesh_generator_uses_settings(self):
        proc = ConcreteMeshProcessor(base_thickness=4.0, z_scale=2.5, target_size_mm=100.0)
        mg = proc._make_mesh_generator()
        assert isinstance(mg, MeshGenerator)
        assert mg.base_thickness == 4.0
        assert mg.z_scale == 2.5
        assert mg.target_size_mm == 100.0

    def test_default_settings(self):
        proc = ConcreteMeshProcessor()
        assert proc.base_thickness == 3.0
        assert proc.z_scale == 1.5
        assert proc.target_size_mm is None

    def test_build_meshes_returns_dict(self):
        proc = ConcreteMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        result = proc.build_meshes(elevation, transform)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            MeshProcessor()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# GradientMeshProcessor
# ---------------------------------------------------------------------------

class TestGradientMeshProcessor:
    def test_returns_three_keys(self):
        proc = GradientMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        assert set(meshes.keys()) == {"base_terrain", "green_inlay", "bunker_cutout"}

    def test_all_values_are_trimesh(self):
        proc = GradientMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert isinstance(mesh, trimesh.Trimesh), f"{name} is not a Trimesh"

    def test_all_meshes_have_vertices(self):
        proc = GradientMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert len(mesh.vertices) > 0, f"{name} has no vertices"

    def test_settings_propagated_to_mesh_generator(self):
        proc = GradientMeshProcessor(base_thickness=5.0, z_scale=2.0, target_size_mm=200.0)
        mg = proc._make_mesh_generator()
        assert mg.base_thickness == 5.0
        assert mg.z_scale == 2.0
        assert mg.target_size_mm == 200.0

    def test_nan_filled_gracefully(self):
        elevation = _terrain_elevation()
        elevation[5, 5] = np.nan
        proc = GradientMeshProcessor()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert not np.any(np.isnan(mesh.vertices)), f"{name} has NaN vertices"

    def test_target_size_scales_base_terrain(self):
        target_mm = 150.0
        proc = GradientMeshProcessor(target_size_mm=target_mm)
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        extents = meshes["base_terrain"].bounding_box.extents
        max_xy = max(extents[0], extents[1])
        assert abs(max_xy - target_mm) < 1.0


# ---------------------------------------------------------------------------
# LoGMeshProcessor
# ---------------------------------------------------------------------------

class TestLoGMeshProcessor:
    def test_returns_three_keys(self):
        proc = LoGMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        assert set(meshes.keys()) == {"base_terrain", "green_inlay", "bunker_cutout"}

    def test_all_values_are_trimesh(self):
        proc = LoGMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert isinstance(mesh, trimesh.Trimesh), f"{name} is not a Trimesh"

    def test_all_meshes_have_vertices(self):
        proc = LoGMeshProcessor()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert len(mesh.vertices) > 0, f"{name} has no vertices"

    def test_settings_propagated_to_mesh_generator(self):
        proc = LoGMeshProcessor(base_thickness=2.0, z_scale=3.0, target_size_mm=100.0)
        mg = proc._make_mesh_generator()
        assert mg.base_thickness == 2.0
        assert mg.z_scale == 3.0
        assert mg.target_size_mm == 100.0

    def test_nan_filled_gracefully(self):
        elevation = _terrain_elevation()
        elevation[5, 5] = np.nan
        proc = LoGMeshProcessor()
        transform = _flat_transform()
        meshes = proc.build_meshes(elevation, transform)
        for name, mesh in meshes.items():
            assert not np.any(np.isnan(mesh.vertices)), f"{name} has NaN vertices"
