"""
Tests for MeshGenerator.generate_layers() and the new Exporter layer methods.
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile

import numpy as np
import pytest
import rasterio.transform
import trimesh

from src.exporter import Exporter
from src.mesh_generator import MeshGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_transform(rows: int = 20, cols: int = 20) -> rasterio.transform.Affine:
    return rasterio.transform.from_bounds(0.0, 0.0, 1.0, 1.0, cols, rows)


def _terrain_elevation(rows: int = 20, cols: int = 20) -> np.ndarray:
    """Synthetic elevation with a raised central plateau and edge depressions."""
    z = np.ones((rows, cols), dtype=np.float64) * 50.0
    # Central plateau (green-like) – higher and flat.
    r_mid, c_mid = rows // 2, cols // 2
    z[r_mid - 2 : r_mid + 3, c_mid - 2 : c_mid + 3] = 60.0
    # Corner depressions (bunker-like) – lower.
    z[0:3, 0:3] = 35.0
    z[0:3, -3:] = 35.0
    return z


# ---------------------------------------------------------------------------
# Tests for MeshGenerator.generate_layers()
# ---------------------------------------------------------------------------

class TestMeshGeneratorGenerateLayers:
    def test_returns_dict_with_three_keys(self):
        gen = MeshGenerator()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        layers = gen.generate_layers(elevation, transform)
        assert set(layers.keys()) == {"base_terrain", "green_inlay", "bunker_cutout"}

    def test_all_layers_are_trimesh_instances(self):
        gen = MeshGenerator()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        layers = gen.generate_layers(elevation, transform)
        for name, mesh in layers.items():
            assert isinstance(mesh, trimesh.Trimesh), (
                f"Layer '{name}' is not a trimesh.Trimesh"
            )

    def test_all_layers_have_vertices_and_faces(self):
        gen = MeshGenerator()
        elevation = _terrain_elevation()
        transform = _flat_transform()
        layers = gen.generate_layers(elevation, transform)
        for name, mesh in layers.items():
            assert len(mesh.vertices) > 0, f"Layer '{name}' has no vertices"
            assert len(mesh.faces) > 0, f"Layer '{name}' has no faces"

    def test_base_terrain_matches_full_generate(self):
        """base_terrain layer should equal a direct generate() call."""
        gen = MeshGenerator(z_scale=1.0, base_thickness=2.0)
        elevation = _terrain_elevation()
        transform = _flat_transform()

        layers = gen.generate_layers(elevation, transform)
        full_mesh = gen.generate(elevation, transform)

        # Same vertex count and face count.
        assert len(layers["base_terrain"].vertices) == len(full_mesh.vertices)
        assert len(layers["base_terrain"].faces) == len(full_mesh.faces)

    def test_no_nan_in_any_layer_vertices(self):
        gen = MeshGenerator()
        elevation = _terrain_elevation()
        elevation[5, 5] = np.nan
        transform = _flat_transform()
        layers = gen.generate_layers(elevation, transform)
        for name, mesh in layers.items():
            assert not np.any(np.isnan(mesh.vertices)), (
                f"Layer '{name}' contains NaN vertices"
            )

    def test_layers_with_z_scale_applied(self):
        """z_scale should influence all three layer meshes."""
        elevation = _terrain_elevation()
        transform = _flat_transform()

        gen1 = MeshGenerator(z_scale=1.0, base_thickness=0)
        gen2 = MeshGenerator(z_scale=3.0, base_thickness=0)

        layers1 = gen1.generate_layers(elevation, transform)
        layers2 = gen2.generate_layers(elevation, transform)

        z_range1 = float(np.max(layers1["base_terrain"].vertices[:, 2]) - np.min(layers1["base_terrain"].vertices[:, 2]))
        z_range2 = float(np.max(layers2["base_terrain"].vertices[:, 2]) - np.min(layers2["base_terrain"].vertices[:, 2]))
        assert z_range2 > z_range1

    def test_target_size_applied_to_all_layers(self):
        """target_size_mm rescaling should apply to all layers."""
        target_mm = 150.0
        gen = MeshGenerator(target_size_mm=target_mm)
        elevation = _terrain_elevation()
        transform = _flat_transform()
        layers = gen.generate_layers(elevation, transform)

        for name, mesh in layers.items():
            extents = mesh.bounding_box.extents
            max_xy = max(extents[0], extents[1])
            assert abs(max_xy - target_mm) < 1.0, (
                f"Layer '{name}': expected {target_mm} mm, got {max_xy:.2f}"
            )


# ---------------------------------------------------------------------------
# Tests for Exporter layer methods
# ---------------------------------------------------------------------------

class TestExporterLayerMethods:
    def _make_simple_mesh(self) -> trimesh.Trimesh:
        verts = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0], [0.5, 0.5, 1.0]], dtype=float)
        faces = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=np.int32)
        return trimesh.Trimesh(vertices=verts, faces=faces)

    def _make_meshes(self) -> dict:
        m = self._make_simple_mesh()
        return {"base_terrain": m, "green_inlay": m, "bunker_cutout": m}

    # -- export_layers_to_dir ------------------------------------------------

    def test_export_layers_to_dir_creates_three_stls(self):
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, "layers")
            Exporter().export_layers_to_dir(meshes, out_dir)
            files = os.listdir(out_dir)
            assert "base_terrain.stl" in files
            assert "green_inlay.stl" in files
            assert "bunker_cutout.stl" in files

    def test_export_layers_to_dir_creates_dir_if_missing(self):
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, "deep", "nested", "layers")
            Exporter().export_layers_to_dir(meshes, out_dir)
            assert os.path.isdir(out_dir)

    def test_export_layers_to_dir_files_are_nonzero(self):
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            Exporter().export_layers_to_dir(meshes, tmp)
            for name in meshes:
                path = os.path.join(tmp, f"{name}.stl")
                assert os.path.getsize(path) > 0, f"{name}.stl is empty"

    # -- export_layers_to_zip ------------------------------------------------

    def test_export_layers_to_zip_creates_zip(self):
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "layers.zip")
            Exporter().export_layers_to_zip(meshes, zip_path)
            assert os.path.exists(zip_path)
            assert zipfile.is_zipfile(zip_path)

    def test_export_layers_to_zip_contains_three_stls(self):
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "layers.zip")
            Exporter().export_layers_to_zip(meshes, zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            assert "base_terrain.stl" in names
            assert "green_inlay.stl" in names
            assert "bunker_cutout.stl" in names

    def test_export_layers_to_zip_creates_parent_dir(self):
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "nested", "output.zip")
            Exporter().export_layers_to_zip(meshes, zip_path)
            assert os.path.exists(zip_path)

    def test_zip_stls_are_valid(self):
        """STL files inside the ZIP can be re-loaded as trimesh objects."""
        meshes = self._make_meshes()
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "layers.zip")
            Exporter().export_layers_to_zip(meshes, zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                for name in meshes:
                    data = zf.read(f"{name}.stl")
                    loaded = trimesh.load(io.BytesIO(data), file_type="stl")
                    assert len(loaded.faces) > 0
