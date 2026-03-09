"""Abstract base class for all output writers.

An :class:`OutputWriter` receives the dictionary of named
:class:`trimesh.Trimesh` objects produced by a
:class:`~src.processors.base.MeshProcessor` and writes them to the
requested *output_path* in whatever format or structure the implementation
defines.

Implementing a custom output writer
-------------------------------------
Sub-class :class:`OutputWriter`, implement :meth:`write`, and pass an
instance to :class:`~src.generators.base.HoleGenerator` (or any concrete
generator) at construction time::

    from src.outputs.base import OutputWriter

    class MyOutput(OutputWriter):
        def write(self, meshes, output_path):
            for name, mesh in meshes.items():
                mesh.export(f"{output_path}_{name}.obj", file_type="obj")

    from src.generators.factory import create_generator
    gen = create_generator(output_writer=MyOutput())
    gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/out/hole")
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class OutputWriter(ABC):
    """Abstract base for pipeline output strategies.

    A writer receives the complete ``name → Trimesh`` mapping produced by
    the :class:`~src.processors.base.MeshProcessor` stage and persists the
    meshes in whatever format or directory structure the implementation
    defines.
    """

    @abstractmethod
    def write(self, meshes: dict, output_path: str) -> None:
        """Persist *meshes* to *output_path*.

        Parameters
        ----------
        meshes:
            Mapping of layer name → :class:`trimesh.Trimesh` produced by
            the processor stage.
        output_path:
            Destination path.  The interpretation (directory, ZIP file,
            …) is left to the concrete implementation.
        """
