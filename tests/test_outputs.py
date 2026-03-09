"""
Tests for the outputs package.

Covers:
* OutputWriter abstract interface.
* LayeredSTLOutput – directory mode and ZIP mode.
"""

from __future__ import annotations

import os
import tempfile
import zipfile

import numpy as np
import pytest
import rasterio.transform
import trimesh

from src.outputs.base import OutputWriter
from src.outputs.layered_stl_output import LayeredSTLOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_transform() -> rasterio.transform.Affine:
    return rasterio.transform.from_bounds(0.0, 0.0, 1.0, 1.0, 10, 10)


def _simple_mesh() -> trimesh.Trimesh:
    """Return a minimal watertight box mesh."""
    return trimesh.creation.box()


def _three_layer_meshes() -> dict:
    return {
        "base_terrain": _simple_mesh(),
        "green_inlay": _simple_mesh(),
        "bunker_cutout": _simple_mesh(),
    }


# ---------------------------------------------------------------------------
# OutputWriter abstract interface
# ---------------------------------------------------------------------------

class TestOutputWriterAbstract:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            OutputWriter()  # type: ignore[abstract]

    def test_concrete_subclass_requires_write_implementation(self):
        """A subclass that does not implement write() must still be abstract."""
        class Incomplete(OutputWriter):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_can_be_instantiated(self):
        class ConcreteWriter(OutputWriter):
            def write(self, meshes, output_path):
                pass  # no-op

        writer = ConcreteWriter()
        assert isinstance(writer, OutputWriter)


# ---------------------------------------------------------------------------
# LayeredSTLOutput – directory mode
# ---------------------------------------------------------------------------

class TestLayeredSTLOutputDirectory:
    def test_creates_output_directory(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers")
            writer.write(_three_layer_meshes(), out)
            assert os.path.isdir(out)

    def test_writes_three_stl_files(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers")
            writer.write(_three_layer_meshes(), out)
            stls = sorted(f for f in os.listdir(out) if f.endswith(".stl"))
            assert stls == ["base_terrain.stl", "bunker_cutout.stl", "green_inlay.stl"]

    def test_stl_files_are_non_empty(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers")
            writer.write(_three_layer_meshes(), out)
            for stl in os.listdir(out):
                path = os.path.join(out, stl)
                assert os.path.getsize(path) > 0, f"{stl} is empty"

    def test_custom_layer_names(self):
        writer = LayeredSTLOutput()
        meshes = {"terrain": _simple_mesh(), "features": _simple_mesh()}
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "custom")
            writer.write(meshes, out)
            stls = sorted(f for f in os.listdir(out) if f.endswith(".stl"))
            assert stls == ["features.stl", "terrain.stl"]


# ---------------------------------------------------------------------------
# LayeredSTLOutput – ZIP mode
# ---------------------------------------------------------------------------

class TestLayeredSTLOutputZip:
    def test_creates_zip_file(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers.zip")
            writer.write(_three_layer_meshes(), out)
            assert os.path.isfile(out)

    def test_zip_contains_three_stls(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers.zip")
            writer.write(_three_layer_meshes(), out)
            with zipfile.ZipFile(out) as zf:
                names = sorted(zf.namelist())
            assert names == ["base_terrain.stl", "bunker_cutout.stl", "green_inlay.stl"]

    def test_zip_stls_are_non_empty(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers.zip")
            writer.write(_three_layer_meshes(), out)
            with zipfile.ZipFile(out) as zf:
                for name in zf.namelist():
                    assert zf.getinfo(name).file_size > 0, f"{name} in ZIP is empty"

    def test_zip_stls_are_valid(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "layers.zip")
            writer.write(_three_layer_meshes(), out)
            with zipfile.ZipFile(out) as zf:
                for name in zf.namelist():
                    data = zf.read(name)
                    mesh = trimesh.load(
                        trimesh.util.wrap_as_stream(data), file_type="stl"
                    )
                    assert isinstance(mesh, trimesh.Trimesh)

    def test_zip_creates_parent_directory(self):
        writer = LayeredSTLOutput()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "nested", "dir", "layers.zip")
            writer.write(_three_layer_meshes(), out)
            assert os.path.isfile(out)
