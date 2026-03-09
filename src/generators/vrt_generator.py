"""VRT-based hole generator.

Produces 3D hole models from a local directory of DTM tile files by:

1. Building (or reusing) a GDAL Virtual Raster (``index.vrt``) over all
   tiles in the configured directory.
2. Clipping the raster to a study-area derived from the given coordinate
   and (optionally) the hole's OSM geometry.
3. Delegating mesh construction to the configured
   :class:`~src.processors.base.MeshProcessor` (defaults to
   :class:`~src.processors.gradient_processor.GradientMeshProcessor` which
   uses a gradient/threshold approach to identify greens and bunkers).

Usage
-----
::

    from src.generators.vrt_generator import VRTHoleGenerator

    gen = VRTHoleGenerator("/data/milton", base_thickness=3.0)
    gen.generate(lat=43.5123, lon=-79.8765, buffer_m=50,
                 output_path="/output/hole3", label="hole-3")
"""

from __future__ import annotations

from typing import Optional, Tuple

import click
import numpy as np
import rasterio.transform

from ..dtm_processor import DTMProcessor
from ..geo_utils import buffer_wgs84_geometry, coordinate_to_study_area
from ..outputs.base import OutputWriter
from ..processors.base import MeshProcessor
from ..processors.gradient_processor import GradientMeshProcessor
from ..vrt_builder import VRTBuilder
from .base import HoleGenerator


class VRTHoleGenerator(HoleGenerator):
    """Generate hole models from local DTM tile files via a GDAL VRT index.

    Parameters
    ----------
    dtm_dir:
        Path to a directory containing DTM/DEM tile files (e.g. ``.img``
        or ``.tif``).  A ``index.vrt`` is built automatically on the first
        call if it does not already exist.
    base_thickness:
        Solid base depth in metres.
    z_scale:
        Vertical exaggeration factor.
    target_size_mm:
        Optional print-bed size (longest XY → this many mm).
    processor:
        :class:`~src.processors.base.MeshProcessor` to use for building
        meshes.  Defaults to
        :class:`~src.processors.gradient_processor.GradientMeshProcessor`.
    output_writer:
        :class:`~src.outputs.base.OutputWriter` to use for persisting
        meshes.  Defaults to
        :class:`~src.outputs.layered_stl_output.LayeredSTLOutput`.
    """

    def __init__(
        self,
        dtm_dir: str,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        target_size_mm: Optional[float] = None,
        processor: Optional[MeshProcessor] = None,
        output_writer: Optional[OutputWriter] = None,
    ) -> None:
        super().__init__(
            base_thickness=base_thickness,
            z_scale=z_scale,
            target_size_mm=target_size_mm,
            processor=processor,
            output_writer=output_writer,
        )
        self.dtm_dir = dtm_dir
        if self.processor is None:
            self.processor = GradientMeshProcessor(
                base_thickness=base_thickness,
                z_scale=z_scale,
                target_size_mm=target_size_mm,
            )

    # ------------------------------------------------------------------
    # HoleGenerator interface
    # ------------------------------------------------------------------

    def acquire_elevation(
        self,
        lat: float,
        lon: float,
        buffer_m: float,
        geometry=None,
        label: str = "",
    ) -> Tuple[np.ndarray, rasterio.transform.Affine]:
        """Build (or reuse) the VRT, then clip elevation to the study area.

        The clip geometry is the intersection of the buffered *geometry* and
        a ~200 m × 200 m bounding box centred on (*lat*, *lon*).  If no
        *geometry* is supplied the 200 m study area is used directly.

        Parameters
        ----------
        lat:
            Latitude of the study-area centre (WGS-84 decimal degrees).
        lon:
            Longitude of the study-area centre (WGS-84 decimal degrees).
        buffer_m:
            Metres to buffer the hole geometry before intersecting with the
            study area.
        geometry:
            Optional Shapely polygon for the golf hole in WGS-84.
        label:
            Human-readable label for log messages.

        Returns
        -------
        Tuple ``(elevation_array, affine_transform)``.
        """
        builder = VRTBuilder(self.dtm_dir)
        vrt_path = builder.ensure_vrt()
        click.echo(f"  VRT index: {vrt_path}")

        study_area = coordinate_to_study_area(lat, lon)

        if geometry is not None:
            buffered_hole = buffer_wgs84_geometry(geometry, buffer_m)
            clip_geom = buffered_hole.intersection(study_area)
            if clip_geom.is_empty:
                clip_geom = study_area
        else:
            clip_geom = study_area

        click.echo(f"  Clipping VRT to {label} study area …")
        with DTMProcessor(vrt_path) as proc:
            elevation, transform = proc.clip_to_geometry(clip_geom)

        return elevation, transform
