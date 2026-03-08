"""Ontario ArcGIS ImageServer hole generator.

Produces 3D hole models without any local files by:

1. Fetching a 32-bit float GeoTIFF from the Ontario DTM LiDAR-Derived
   ImageServer via :class:`~src.services.ontario_geohub.OntarioGeohubClient`.
2. Optionally clipping the raster to an OSM hole geometry.
3. Running :class:`~src.services.feature_extractor.FeatureExtractor` (which
   uses a Laplacian-of-Gaussian filter) to identify greens/tees and bunkers
   directly from the raw elevation data.

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
from ..mesh_generator import MeshGenerator
from ..services.feature_extractor import FeatureExtractor
from ..services.ontario_geohub import OntarioGeohubClient
from .base import HoleGenerator


class ImageServerHoleGenerator(HoleGenerator):
    """Generate hole models by fetching elevation from Ontario ArcGIS ImageServer.

    No local DTM files are required.  Elevation data is downloaded on-demand
    as a 32-bit float GeoTIFF and stored only for the duration of processing.

    Feature segmentation uses the Laplacian-of-Gaussian approach implemented
    in :class:`~src.services.feature_extractor.FeatureExtractor`:

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
    """

    def __init__(
        self,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        target_size_mm: Optional[float] = None,
    ) -> None:
        super().__init__(base_thickness, z_scale, target_size_mm)
        self._client = OntarioGeohubClient()

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

    def build_meshes(
        self,
        elevation: np.ndarray,
        transform: rasterio.transform.Affine,
    ) -> dict:
        """Build three layer meshes using LoG-based feature extraction.

        Uses :class:`~src.services.feature_extractor.FeatureExtractor` to
        produce green and bunker masks, then builds watertight meshes for
        each layer with :class:`~src.mesh_generator.MeshGenerator`.

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
