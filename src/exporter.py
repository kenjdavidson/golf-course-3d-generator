"""
Mesh exporter.

Exports a :class:`trimesh.Trimesh` to common 3D formats used for
3D printing (STL, OBJ).
"""

from __future__ import annotations

import os
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
    """Export a trimesh mesh to disk."""

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
