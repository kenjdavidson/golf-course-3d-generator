"""Gradient / threshold mesh processor.

Produces three layer meshes using the gradient-magnitude approach that is
native to the local VRT / DTM tile pipeline:

* ``base_terrain`` – full terrain surface (structural body).
* ``green_inlay``  – flat elevated plateaus (low slope + at-or-above median).
* ``bunker_cutout``– local depressions (below ``median − 0.5 × std``).

This is the default processor used by
:class:`~src.generators.vrt_generator.VRTHoleGenerator`.

Usage
-----
::

    from src.processors.gradient_processor import GradientMeshProcessor

    processor = GradientMeshProcessor(base_thickness=3.0, z_scale=1.5)
    meshes = processor.build_meshes(elevation, transform)
    # meshes.keys() == {"base_terrain", "green_inlay", "bunker_cutout"}
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import rasterio.transform

from .base import MeshProcessor


class GradientMeshProcessor(MeshProcessor):
    """Build layer meshes using the gradient / threshold approach.

    Identifies *greens / tee areas* as flat plateaus at or above the median
    elevation (low gradient magnitude + elevation ≥ median) and *bunkers* as
    depressions below ``median − 0.5 × std``.  The classification is done
    entirely from the elevation grid — no external feature data is required.

    This processor delegates layer triangulation to
    :meth:`~src.mesh_generator.MeshGenerator.generate_layers`.

    Parameters
    ----------
    base_thickness:
        Solid base depth in metres.
    z_scale:
        Vertical exaggeration factor.
    target_size_mm:
        Optional print-bed rescaling (longest XY → this many mm).
    """

    def __init__(
        self,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        target_size_mm: Optional[float] = None,
    ) -> None:
        super().__init__(base_thickness, z_scale, target_size_mm)

    def build_meshes(
        self,
        elevation: np.ndarray,
        transform: rasterio.transform.Affine,
    ) -> dict:
        """Build three layer meshes using gradient-magnitude thresholding.

        Delegates to :meth:`~src.mesh_generator.MeshGenerator.generate_layers`
        which identifies greens (low slope + high elevation) and bunkers
        (below median − 0.5 × std).

        Parameters
        ----------
        elevation:
            2-D float array of elevation values (rows × cols).
        transform:
            Rasterio affine transform.

        Returns
        -------
        dict
            Keys ``"base_terrain"``, ``"green_inlay"``, ``"bunker_cutout"``.
        """
        return self._make_mesh_generator().generate_layers(elevation, transform)
