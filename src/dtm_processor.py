"""
DTM (Digital Terrain Model) processor.

Overview
--------
This module provides :class:`DTMProcessor`, which opens a GeoTIFF
elevation raster (DEM / DTM), optionally reprojects a clipping geometry
into the raster's coordinate reference system (CRS), and returns a
NumPy elevation array ready for mesh generation.

Required input files
--------------------
A **GeoTIFF** file containing single-band floating-point (or integer)
elevation data in metres.  Any coordinate reference system supported by
GDAL is accepted; the processor re-projects query geometries into the
raster's native CRS automatically.

Where to obtain DTM data
------------------------
Several free, global or regional datasets are available:

* **USGS 3DEP (USA)** – 1-m and 1/3 arc-second resolution.
  Download via the National Map: https://apps.nationalmap.gov/downloader/

* **Copernicus DEM** – 30-m global coverage from the EU Space Programme.
  https://spacedata.copernicus.eu/

* **OpenTopography** – aggregates many public LiDAR and SRTM datasets.
  https://opentopography.org/

* **SRTM (NASA)** – 30-m global coverage, available on many mirror sites.

Place the downloaded ``.tif`` file in the ``data/`` directory of this
project (bind-mounted to ``/data`` inside the Docker container).

Example usage
-------------
Using the context manager (recommended)::

    from src.dtm_processor import DTMProcessor
    from shapely.geometry import box

    # A polygon covering the golf hole plus a surrounding buffer
    hole_geom = box(-74.005, 40.701, -74.001, 40.709)

    with DTMProcessor("/data/terrain.tif") as proc:
        print(proc.crs)           # e.g. EPSG:4326
        print(proc.bounds)        # BoundingBox(left=…, bottom=…, …)
        elevation, transform = proc.clip_to_geometry(hole_geom)
        # elevation: np.ndarray, shape (rows, cols), values in metres
        # transform: rasterio Affine mapping pixels → CRS coordinates

Using a WGS-84 bounding box shortcut::

    with DTMProcessor("/data/terrain.tif") as proc:
        elevation, transform = proc.clip_to_bounds(
            (-74.01, 40.69, -73.99, 40.73)  # (west, south, east, north)
        )

Manual open / close (useful when keeping the file open across many clips)::

    proc = DTMProcessor("/data/terrain.tif")
    proc.open()
    try:
        elev, tf = proc.clip_to_geometry(geom)
    finally:
        proc.close()

Notes
-----
* Pixels that fall outside the clip geometry or that carry the raster's
  ``nodata`` value are replaced with ``np.nan`` in the returned array.
* The geometry passed to :meth:`clip_to_geometry` is assumed to be in
  ``EPSG:4326`` (WGS-84 lon/lat) by default.  Pass a different
  ``geometry_crs`` string if your geometry is in another CRS.
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
    """Load and query a GeoTIFF DTM raster.

    Parameters
    ----------
    dtm_path:
        Absolute or relative path to a GeoTIFF elevation file.  Inside the
        Docker container this is typically ``/data/<filename>.tif`` because
        the ``data/`` directory is bind-mounted to ``/data`` (read-only).

    Examples
    --------
    >>> from shapely.geometry import box
    >>> with DTMProcessor("/data/terrain.tif") as proc:
    ...     elevation, transform = proc.clip_to_geometry(
    ...         box(-74.005, 40.701, -74.001, 40.709)
    ...     )
    """

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
