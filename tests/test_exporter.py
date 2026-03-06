"""
Tests for Exporter.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest
import trimesh

from src.exporter import ExportFormat, Exporter


def _simple_mesh() -> trimesh.Trimesh:
    """Return a trivial triangle mesh for testing."""
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.5, 1.0, 0.0],
        [0.5, 0.5, 1.0],
    ], dtype=float)
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces)


class TestExportFormat:
    def test_from_path_stl(self):
        fmt = ExportFormat.from_path("/output/hole.stl")
        assert fmt == ExportFormat.STL

    def test_from_path_obj(self):
        fmt = ExportFormat.from_path("/output/hole.OBJ")
        assert fmt == ExportFormat.OBJ

    def test_from_path_unknown_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            ExportFormat.from_path("/output/hole.abc")


class TestExporter:
    def test_export_stl_creates_file(self):
        mesh = _simple_mesh()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hole.stl")
            Exporter().export(mesh, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_export_obj_creates_file(self):
        mesh = _simple_mesh()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hole.obj")
            Exporter().export(mesh, path, fmt=ExportFormat.OBJ)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_export_creates_parent_dir_if_missing(self):
        mesh = _simple_mesh()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "deep", "hole.stl")
            Exporter().export(mesh, path)
            assert os.path.exists(path)

    def test_stl_is_valid_binary_stl(self):
        mesh = _simple_mesh()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hole.stl")
            Exporter().export(mesh, path)
            reloaded = trimesh.load(path)
            assert len(reloaded.faces) == len(mesh.faces)
