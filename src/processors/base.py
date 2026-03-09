"""Abstract base class for all mesh processors.

A :class:`MeshProcessor` converts a 2-D elevation array and its rasterio
affine transform into a dictionary of named :class:`trimesh.Trimesh` objects
(one per print layer).

Implementing a custom processor
--------------------------------
Sub-class :class:`MeshProcessor`, implement :meth:`build_meshes`, and pass
an instance to :class:`~src.generators.base.HoleGenerator` (or any concrete
generator) at construction time::

    from src.processors.base import MeshProcessor
    from src.mesh_generator import MeshGenerator

    class MyProcessor(MeshProcessor):
        def build_meshes(self, elevation, transform):
            gen = self._make_mesh_generator()
            return {"base_terrain": gen.generate(elevation, transform)}

    from src.generators.factory import create_generator
    gen = create_generator(dtm_dir="/data", processor=MyProcessor())
    gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/out/hole")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import rasterio.transform

from ..mesh_generator import MeshGenerator


class MeshProcessor(ABC):
    """Abstract base for mesh-building strategies.

    A processor takes a raw elevation grid and its spatial transform and
    returns a dictionary of named :class:`trimesh.Trimesh` objects suitable
    for 3D printing.  Different processors can apply different feature
    detection and layer-construction strategies without touching the
    elevation acquisition or file-export stages of the pipeline.

    Parameters
    ----------
    base_thickness:
        Solid base depth in metres added below the terrain surface.
    z_scale:
        Vertical exaggeration factor applied to terrain relief.
    target_size_mm:
        If given, the longest XY dimension of every mesh is rescaled to
        this value in millimetres.
    """

    def __init__(
        self,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        target_size_mm: Optional[float] = None,
    ) -> None:
        self.base_thickness = base_thickness
        self.z_scale = z_scale
        self.target_size_mm = target_size_mm

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def build_meshes(
        self,
        elevation: np.ndarray,
        transform: rasterio.transform.Affine,
    ) -> dict:
        """Convert *elevation* into a ``name → Trimesh`` mapping.

        Parameters
        ----------
        elevation:
            2-D float array of elevation values (rows × cols).
            ``np.nan`` values indicate no-data pixels.
        transform:
            Rasterio affine transform mapping pixel (col, row) → (x, y)
            in the raster's coordinate reference system.

        Returns
        -------
        dict
            Mapping of layer name to :class:`trimesh.Trimesh`.  The keys
            returned depend on the concrete implementation; typical keys
            are ``"base_terrain"``, ``"green_inlay"``, and
            ``"bunker_cutout"``.
        """

    # ------------------------------------------------------------------
    # Shared helper
    # ------------------------------------------------------------------

    def _make_mesh_generator(self) -> MeshGenerator:
        """Return a :class:`~src.mesh_generator.MeshGenerator` configured from this processor's settings."""
        return MeshGenerator(
            base_thickness=self.base_thickness,
            z_scale=self.z_scale,
            target_size_mm=self.target_size_mm,
        )
