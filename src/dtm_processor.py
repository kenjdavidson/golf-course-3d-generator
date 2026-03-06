"""
DTM (Digital Terrain Model) processor.

Reads GeoTIFF elevation rasters and extracts clipped elevation arrays
for a given geographic region.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from pyproj import Transformer
from shapely.geometry import box, mapping
from shapely.ops import transform as shapely_transform
from shapely.geometry.base import BaseGeometry


class DTMProcessor:
    """Load and query a GeoTIFF DTM raster."""

    def __init__(self, dtm_path: str) -> None:
        self.dtm_path = dtm_path
        self._dataset: Optional[rasterio.DatasetReader] = None

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "DTMProcessor":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------

    def open(self) -> "DTMProcessor":
        """Open the DTM raster file."""
        self._dataset = rasterio.open(self.dtm_path)
        return self

    def close(self) -> None:
        """Close the underlying raster dataset."""
        if self._dataset is not None:
            self._dataset.close()
            self._dataset = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def crs(self):
        """Coordinate reference system of the DTM."""
        self._require_open()
        return self._dataset.crs

    @property
    def bounds(self) -> rasterio.coords.BoundingBox:
        """Geographic bounds of the DTM."""
        self._require_open()
        return self._dataset.bounds

    @property
    def resolution(self) -> Tuple[float, float]:
        """Pixel resolution (x_res, y_res) in the DTM's native CRS units."""
        self._require_open()
        return self._dataset.res  # (y_res, x_res) — rasterio convention

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def clip_to_geometry(
        self,
        geometry: BaseGeometry,
        geometry_crs: str = "EPSG:4326",
    ) -> Tuple[np.ndarray, rasterio.transform.Affine]:
        """Clip the DTM to *geometry* and return the elevation array + transform.

        Parameters
        ----------
        geometry:
            A Shapely geometry defining the region of interest.
        geometry_crs:
            CRS of *geometry* as an EPSG string (default ``"EPSG:4326"``).

        Returns
        -------
        elevation : np.ndarray, shape (rows, cols)
            Elevation values in the DTM's native units (usually metres).
            Pixels outside *geometry* or with no-data values are ``np.nan``.
        transform : rasterio.transform.Affine
            Affine transform mapping pixel coordinates to the DTM's CRS.
        """
        self._require_open()

        projected_geom = self._reproject_geometry(geometry, geometry_crs)

        clipped, transform = rasterio_mask(
            self._dataset,
            [mapping(projected_geom)],
            crop=True,
            filled=True,
        )

        elevation = clipped[0].astype(float)

        nodata = self._dataset.nodata
        if nodata is not None:
            elevation[elevation == nodata] = np.nan

        return elevation, transform

    def clip_to_bounds(
        self,
        bounds_wgs84: Tuple[float, float, float, float],
    ) -> Tuple[np.ndarray, rasterio.transform.Affine]:
        """Clip the DTM to a WGS-84 bounding box ``(west, south, east, north)``.

        Returns the same (elevation, transform) pair as :meth:`clip_to_geometry`.
        """
        west, south, east, north = bounds_wgs84
        geometry = box(west, south, east, north)
        return self.clip_to_geometry(geometry, geometry_crs="EPSG:4326")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if self._dataset is None:
            raise RuntimeError(
                "DTMProcessor is not open. Call open() or use it as a context manager."
            )

    def _reproject_geometry(
        self, geometry: BaseGeometry, from_crs: str
    ) -> BaseGeometry:
        """Reproject *geometry* from *from_crs* into the DTM's CRS."""
        dtm_crs_str = self._dataset.crs.to_string()
        if from_crs == dtm_crs_str:
            return geometry

        transformer = Transformer.from_crs(
            from_crs, dtm_crs_str, always_xy=True
        )
        return shapely_transform(transformer.transform, geometry)
