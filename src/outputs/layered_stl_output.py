"""Layered STL output writer.

Writes each mesh in the ``name → Trimesh`` mapping to disk as an STL file.
Two modes are supported:

* **Directory mode** – each mesh is written as ``<name>.stl`` inside the
  directory specified by *output_path*.
* **ZIP mode** – when *output_path* ends in ``.zip``, all meshes are packed
  into a single ZIP archive.

This is the default :class:`~src.outputs.base.OutputWriter` used by all
built-in generators.

Usage
-----
::

    from src.outputs.layered_stl_output import LayeredSTLOutput

    writer = LayeredSTLOutput()
    writer.write(meshes, "/output/hole3")        # directory
    writer.write(meshes, "/output/hole3.zip")    # ZIP archive
"""

from __future__ import annotations

import os

import click

from ..exporter import Exporter
from .base import OutputWriter


class LayeredSTLOutput(OutputWriter):
    """Write layer meshes as STL files to a directory or ZIP archive.

    When *output_path* ends in ``.zip`` all meshes are packed into a
    single archive; otherwise each mesh is written as ``<name>.stl``
    inside the given directory.

    This writer delegates file I/O to :class:`~src.exporter.Exporter`.
    """

    def write(self, meshes: dict, output_path: str) -> None:
        """Persist *meshes* to *output_path*.

        Parameters
        ----------
        meshes:
            Mapping of layer name → :class:`trimesh.Trimesh`.
        output_path:
            Target directory path **or** a path ending in ``.zip`` to
            receive a single archive.
        """
        exporter = Exporter()
        if output_path.endswith(".zip"):
            exporter.export_layers_to_zip(meshes, output_path)
            click.echo(f"  ✓ Layers saved → {output_path}")
        else:
            exporter.export_layers_to_dir(meshes, output_path)
            for name in meshes:
                click.echo(
                    f"  ✓ {name}.stl → {os.path.join(output_path, name + '.stl')}"
                )
