"""Ontario ArcGIS ImageServer hole generator.

Produces 3D hole models without any local files by:

1. Fetching a 32-bit float GeoTIFF from the Ontario DTM LiDAR-Derived
   ImageServer via :class:`~src.services.ontario_geohub.OntarioGeohubClient`.
2. Optionally clipping the raster to an OSM hole geometry.
3. Delegating mesh construction to the configured
   :class:`~src.processors.base.MeshProcessor` (defaults to
   :class:`~src.processors.log_processor.LoGMeshProcessor` which uses a
   Laplacian-of-Gaussian filter to identify greens/tees and bunkers).

Usage
-----
::

    from src.generators.imageserver_generator import ImageServerHoleGenerator

    gen = ImageServerHoleGenerator(base_thickness=3.0)
    gen.generate(lat=43.5123, lon=-79.8765, buffer_m=150,
                 output_path="/output/hole3", label="cloud-hole")
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import click
import numpy as np
import rasterio.transform

from ..dtm_processor import DTMProcessor
from ..outputs.base import OutputWriter
from ..processors.base import MeshProcessor
from ..processors.log_processor import LoGMeshProcessor
from ..services.ontario_geohub import OntarioGeohubClient
from .base import HoleGenerator


class ImageServerHoleGenerator(HoleGenerator):
    """Generate hole models by fetching elevation from Ontario ArcGIS ImageServer.

    No local DTM files are required.  Elevation data is downloaded on-demand
    as a 32-bit float GeoTIFF and stored only for the duration of processing.

    Feature segmentation defaults to the Laplacian-of-Gaussian approach
    implemented in :class:`~src.processors.log_processor.LoGMeshProcessor`:

    * ``green_inlay`` – convex plateaus (negative LoG + slope < 3°).
    * ``bunker_cutout`` – concave depressions (positive LoG + below median).

    Parameters
    ----------
    base_thickness:
        Solid base depth in metres.
    z_scale:
        Vertical exaggeration factor.
    target_size_mm:
        Optional print-bed size (longest XY → this many mm).
    processor:
        :class:`~src.processors.base.MeshProcessor` to use for building
        meshes.  Defaults to
        :class:`~src.processors.log_processor.LoGMeshProcessor`.
    output_writer:
        :class:`~src.outputs.base.OutputWriter` to use for persisting
        meshes.  Defaults to
        :class:`~src.outputs.layered_stl_output.LayeredSTLOutput`.
    """

    def __init__(
        self,
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
        self._client = OntarioGeohubClient()
        if self.processor is None:
            self.processor = LoGMeshProcessor(
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
        """Fetch a GeoTIFF from the ImageServer and return the elevation array.

        A bounding box of ``2 × buffer_m`` metres on each side is computed
        in EPSG:3857, sent to the ImageServer, and the returned GeoTIFF is
        read into a NumPy array.  If a hole *geometry* is provided the raster
        is further clipped to it; otherwise the full fetched extent is used.

        The temporary GeoTIFF file is deleted before this method returns.

        Parameters
        ----------
        lat:
            Latitude of the fetch-area centre (WGS-84 decimal degrees).
        lon:
            Longitude of the fetch-area centre (WGS-84 decimal degrees).
        buffer_m:
            Half-width of the square bounding box in metres (recommend 150).
        geometry:
            Optional Shapely polygon for fine-grained clipping (WGS-84).
        label:
            Human-readable label for log messages.

        Returns
        -------
        Tuple ``(elevation_array, affine_transform)``.
        """
        click.echo(
            f"  Fetching elevation from Ontario ImageServer for {label} "
            f"(buffer={buffer_m} m) …"
        )
        tmp_path = self._client.fetch_elevation_tiff(lat, lon, buffer_m)
        try:
            with DTMProcessor(tmp_path) as proc:
                if geometry is not None:
                    elevation, transform = proc.clip_to_geometry(geometry)
                else:
                    # Clip to the full fetched extent using the raster's native CRS
                    # so we do not trigger a lossy WGS-84 round-trip.
                    from shapely.geometry import box as shapely_box

                    b = proc.bounds
                    native_crs = proc.crs.to_string()
                    native_geom = shapely_box(b.left, b.bottom, b.right, b.top)
                    elevation, transform = proc.clip_to_geometry(
                        native_geom, geometry_crs=native_crs
                    )
        finally:
            os.unlink(tmp_path)

        return elevation, transform
