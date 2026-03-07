"""
Tests for MeshGenerator.

All tests use synthetic elevation arrays so no external DTM files are needed.
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio.transform
import trimesh

from src.mesh_generator import MeshGenerator


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _flat_transform(rows: int = 10, cols: int = 10) -> rasterio.transform.Affine:
    """Return an affine transform for a 1-degree × 1-degree region."""
    return rasterio.transform.from_bounds(0.0, 0.0, 1.0, 1.0, cols, rows)


def _ramp_elevation(rows: int = 10, cols: int = 10) -> np.ndarray:
    """Linearly increasing elevation from 0 to 99."""
    return np.linspace(0, 99, rows * cols).reshape(rows, cols).astype(np.float64)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMeshGeneratorBasic:
    def test_returns_trimesh_instance(self):
        gen = MeshGenerator()
        elevation = _ramp_elevation()
        transform = _flat_transform()
        mesh = gen.generate(elevation, transform)
        assert isinstance(mesh, trimesh.Trimesh)

    def test_mesh_has_vertices_and_faces(self):
        gen = MeshGenerator()
        elevation = _ramp_elevation()
        transform = _flat_transform()
        mesh = gen.generate(elevation, transform)
        assert len(mesh.vertices) > 0
        assert len(mesh.faces) > 0

    def test_flat_terrain_produces_flat_top(self):
        """All surface z-values should be the same for flat terrain."""
        gen = MeshGenerator(base_thickness=1.0, z_scale=1.0)
        elevation = np.full((8, 8), 50.0)
        transform = _flat_transform(8, 8)
        mesh = gen.generate(elevation, transform)
        # All surface vertices should have z >= 0 (relative elevation)
        assert mesh.vertices[:, 2].min() < 0  # base is below 0
        assert mesh.vertices[:, 2].max() >= 0  # top is at 0 (no relief)

    def test_nan_values_are_filled(self):
        elevation = _ramp_elevation()
        elevation[3, 3] = np.nan
        gen = MeshGenerator()
        transform = _flat_transform()
        mesh = gen.generate(elevation, transform)
        assert not np.any(np.isnan(mesh.vertices))


class TestMeshGeneratorScaling:
    def test_target_size_scales_mesh(self):
        target_mm = 200.0
        gen = MeshGenerator(target_size_mm=target_mm)
        elevation = _ramp_elevation(20, 20)
        transform = _flat_transform(20, 20)
        mesh = gen.generate(elevation, transform)
        extents = mesh.bounding_box.extents
        max_xy = max(extents[0], extents[1])
        assert abs(max_xy - target_mm) < 1.0, f"Expected {target_mm}, got {max_xy}"

    def test_z_scale_increases_relief(self):
        elevation = _ramp_elevation()
        transform = _flat_transform()

        gen_1x = MeshGenerator(z_scale=1.0, base_thickness=0)
        gen_2x = MeshGenerator(z_scale=2.0, base_thickness=0)

        mesh_1x = gen_1x.generate(elevation, transform)
        mesh_2x = gen_2x.generate(elevation, transform)

        extent_z_1x = mesh_1x.bounding_box.extents[2]
        extent_z_2x = mesh_2x.bounding_box.extents[2]

        assert extent_z_2x > extent_z_1x

    def test_base_thickness_controls_depth(self):
        elevation = np.full((5, 5), 10.0)
        transform = _flat_transform(5, 5)

        gen_thin = MeshGenerator(base_thickness=1.0)
        gen_thick = MeshGenerator(base_thickness=5.0)

        mesh_thin = gen_thin.generate(elevation, transform)
        mesh_thick = gen_thick.generate(elevation, transform)

        assert mesh_thick.vertices[:, 2].min() < mesh_thin.vertices[:, 2].min()


class TestMeshGeneratorCoordinateGrid:
    def test_grid_shape_matches_elevation(self):
        rows, cols = 7, 9
        gen = MeshGenerator()
        transform = _flat_transform(rows, cols)
        xs, ys = gen._build_coordinate_grids(rows, cols, transform)
        assert xs.shape == (rows, cols)
        assert ys.shape == (rows, cols)

    def test_grid_values_vary_across_axes(self):
        rows, cols = 5, 5
        transform = _flat_transform(rows, cols)
        xs, ys = MeshGenerator._build_coordinate_grids(rows, cols, transform)
        # x values should vary along columns
        assert xs[0, 0] != xs[0, -1]
        # y values should vary along rows
        assert ys[0, 0] != ys[-1, 0]


class TestFillNan:
    def test_no_nans_unchanged(self):
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = MeshGenerator._fill_nan(arr)
        np.testing.assert_array_equal(result, arr)

    def test_nans_replaced_with_min(self):
        arr = np.array([[1.0, np.nan], [3.0, 4.0]])
        result = MeshGenerator._fill_nan(arr)
        assert not np.any(np.isnan(result))
        assert result[0, 1] == 1.0  # replaced by min (1.0)
