"""Output writer abstractions for the golf course 3D generation pipeline.

An :class:`OutputWriter` takes a dictionary of named
:class:`trimesh.Trimesh` objects produced by a
:class:`~src.processors.base.MeshProcessor` and writes them to disk in
whatever format or layout the implementation chooses.

Public classes
--------------
* :class:`~src.outputs.base.OutputWriter` – abstract base class.
* :class:`~src.outputs.layered_stl_output.LayeredSTLOutput` – writes three
  STL files to a directory, or packs them into a ZIP archive.
"""

from .base import OutputWriter
from .layered_stl_output import LayeredSTLOutput

__all__ = ["OutputWriter", "LayeredSTLOutput"]
