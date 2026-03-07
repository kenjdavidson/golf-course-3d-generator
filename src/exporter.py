"""
Mesh exporter.

Exports a :class:`trimesh.Trimesh` to common 3D formats used for
3D printing (STL, OBJ).

For multi-material layer output (from
:meth:`~src.mesh_generator.MeshGenerator.generate_layers`) use
:meth:`Exporter.export_layers_to_dir` or
:meth:`Exporter.export_layers_to_zip`.
"""

from __future__ import annotations

import os
import zipfile
from enum import Enum

import trimesh


class ExportFormat(str, Enum):
    STL = "stl"
    OBJ = "obj"

    @classmethod
    def from_path(cls, path: str) -> "ExportFormat":
        """Infer format from file extension."""
        ext = os.path.splitext(path)[-1].lower().lstrip(".")
        try:
            return cls(ext)
        except ValueError:
            raise ValueError(
                f"Unsupported file extension '.{ext}'. "
                f"Supported formats: {[f.value for f in cls]}"
            )


class Exporter:
    """Export a trimesh mesh (or a collection of named meshes) to disk."""

    def export(
        self,
        mesh: trimesh.Trimesh,
        output_path: str,
        fmt: ExportFormat | None = None,
    ) -> None:
        """Write *mesh* to *output_path*.

        Parameters
        ----------
        mesh:
            The mesh to export.
        output_path:
            Destination file path.  The parent directory must exist.
        fmt:
            Output format.  If ``None``, inferred from the file extension.
        """
        if fmt is None:
            fmt = ExportFormat.from_path(output_path)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        mesh.export(output_path, file_type=fmt.value)

    def export_layers_to_dir(
        self,
        meshes: dict[str, trimesh.Trimesh],
        output_dir: str,
    ) -> None:
        """Write each mesh in *meshes* as an STL file inside *output_dir*.

        The file names are ``<key>.stl`` (e.g. ``base_terrain.stl``,
        ``green_inlay.stl``, ``bunker_cutout.stl``).

        Parameters
        ----------
        meshes:
            Mapping of layer name → :class:`trimesh.Trimesh`.
        output_dir:
            Directory to write into.  Created if it does not exist.
        """
        os.makedirs(output_dir, exist_ok=True)
        for name, mesh in meshes.items():
            path = os.path.join(output_dir, f"{name}.stl")
            mesh.export(path, file_type="stl")

    def export_layers_to_zip(
        self,
        meshes: dict[str, trimesh.Trimesh],
        zip_path: str,
    ) -> None:
        """Pack each mesh in *meshes* into a single ZIP archive.

        Each mesh is written as ``<key>.stl`` inside the archive.

        Parameters
        ----------
        meshes:
            Mapping of layer name → :class:`trimesh.Trimesh`.
        zip_path:
            Destination ``.zip`` file path.  The parent directory is
            created if it does not exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, mesh in meshes.items():
                stl_bytes = mesh.export(file_type="stl")
                zf.writestr(f"{name}.stl", stl_bytes)
