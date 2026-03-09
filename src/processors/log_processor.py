"""Laplacian of Gaussian (LoG) mesh processor.

Produces three layer meshes by applying the LoG-based feature extraction
from :class:`~src.services.feature_extractor.FeatureExtractor`:

* ``base_terrain`` – full terrain surface (structural body).
* ``green_inlay``  – convex plateaus detected via negative LoG + low slope.
* ``bunker_cutout``– concave depressions detected via positive LoG + below median.

This is the default processor used by
:class:`~src.generators.imageserver_generator.ImageServerHoleGenerator`.

Usage
-----
::

    from src.processors.log_processor import LoGMeshProcessor

    processor = LoGMeshProcessor(base_thickness=3.0, z_scale=1.5)
    meshes = processor.build_meshes(elevation, transform)
    # meshes.keys() == {"base_terrain", "green_inlay", "bunker_cutout"}
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import rasterio.transform

from ..mesh_generator import MeshGenerator
from ..services.feature_extractor import FeatureExtractor
from .base import MeshProcessor


class LoGMeshProcessor(MeshProcessor):
    """Build layer meshes using Laplacian of Gaussian feature extraction.

    Uses :class:`~src.services.feature_extractor.FeatureExtractor` to
    produce green and bunker masks directly from the raw elevation data,
    then builds a watertight mesh for each layer with
    :class:`~src.mesh_generator.MeshGenerator`.

    * ``green_inlay`` – convex plateaus (negative LoG + slope < 3°).
    * ``bunker_cutout`` – concave depressions (positive LoG + below median).

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
        """Build three layer meshes using LoG-based feature extraction.

        Uses :class:`~src.services.feature_extractor.FeatureExtractor` to
        produce green and bunker masks, then builds watertight meshes for
        each layer with :class:`~src.mesh_generator.MeshGenerator`.

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
        extractor = FeatureExtractor()
        green_mask = extractor.extract_green_mask(elevation)
        bunker_mask = extractor.extract_bunker_mask(elevation)

        filled = MeshGenerator._fill_nan(elevation)
        green_elev = np.where(green_mask, filled, np.nan)
        bunker_elev = np.where(bunker_mask, filled, np.nan)

        gen = self._make_mesh_generator()
        return {
            "base_terrain": gen.generate(elevation, transform),
            "green_inlay": gen.generate(green_elev, transform),
            "bunker_cutout": gen.generate(bunker_elev, transform),
        }
