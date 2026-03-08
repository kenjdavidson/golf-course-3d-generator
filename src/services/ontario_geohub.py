"""Ontario ArcGIS ImageServer client.

Fetches 32-bit floating-point GeoTIFF elevation data from the Ontario DTM
LiDAR-Derived ImageServer operated by the Ministry of Natural Resources and
Forestry (LRC GeoServices).

Usage
-----
::

    from src.services.ontario_geohub import OntarioGeohubClient

    client = OntarioGeohubClient()
    tmp_path = client.fetch_elevation_tiff(lat=43.5123, lon=-79.8765, buffer_m=150)
    # Use tmp_path with DTMProcessor, then delete it when done.
    import os; os.unlink(tmp_path)

The returned GeoTIFF is in EPSG:3857 (Web Mercator) and uses a 32-bit float
pixel type, making it directly compatible with :class:`~src.dtm_processor.DTMProcessor`.
"""

from __future__ import annotations

import os
import tempfile
from typing import Tuple

import requests
from pyproj import Transformer

_BASE_URL = (
    "https://ws.geoservices.lrc.gov.on.ca/arcgis5/rest/services/"
    "Elevation/Ontario_DTM_LidarDerived/ImageServer/exportImage"
)

# Default image size requested from the server (pixels × pixels).
_DEFAULT_IMAGE_SIZE = 512


class OntarioGeohubClient:
    """Fetch elevation tiles from the Ontario DTM LiDAR-Derived ImageServer.

    Parameters
    ----------
    base_url:
        Full URL of the ArcGIS ImageServer ``exportImage`` endpoint.
        Defaults to the LRC GeoServices production URL.
    timeout:
        HTTP request timeout in seconds.
    image_size:
        Width and height (in pixels) of the requested image.  The server
        returns a square raster at this resolution.
    """

    def __init__(
        self,
        base_url: str = _BASE_URL,
        timeout: int = 60,
        image_size: int = _DEFAULT_IMAGE_SIZE,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.image_size = image_size

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_elevation_tiff(
        self,
        lat: float,
        lon: float,
        buffer_m: float = 150.0,
    ) -> str:
        """Fetch a 32-bit float GeoTIFF for the area around *(lat, lon)*.

        A bounding box of ``2 × buffer_m`` metres on each side is projected
        into EPSG:3857, then sent as the ``bbox`` parameter of an
        ``exportImage`` REST request.  The response body is written to a
        temporary ``.tif`` file whose path is returned.

        Parameters
        ----------
        lat:
            Latitude of the centre point in decimal degrees (WGS-84).
        lon:
            Longitude of the centre point in decimal degrees (WGS-84).
        buffer_m:
            Half-width of the square bounding box in metres.  A value of
            150 produces a 300 m × 300 m fetch area.

        Returns
        -------
        str
            Absolute path to a temporary GeoTIFF file.  The caller is
            responsible for deleting this file when it is no longer needed.

        Raises
        ------
        requests.HTTPError
            If the server returns a non-2xx HTTP status code.
        """
        west, south, east, north = self._compute_bbox_3857(lat, lon, buffer_m)
        size_str = f"{self.image_size},{self.image_size}"

        params = {
            "bbox": f"{west},{south},{east},{north}",
            "bboxSR": "3857",
            "size": size_str,
            "imageSR": "3857",
            "format": "tiff",
            "pixelType": "F32",
            "noDataInterpretation": "esriNoDataMatchAny",
            "interpolation": "+RSP_BilinearInterpolation",
            "f": "image",
        }

        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()

        fd, path = tempfile.mkstemp(suffix=".tif")
        try:
            os.close(fd)
            with open(path, "wb") as fh:
                fh.write(response.content)
        except Exception:
            os.unlink(path)
            raise

        return path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_bbox_3857(
        lat: float, lon: float, buffer_m: float
    ) -> Tuple[float, float, float, float]:
        """Compute a Web Mercator (EPSG:3857) bounding box around *(lat, lon)*.

        Parameters
        ----------
        lat:
            Latitude in decimal degrees (WGS-84).
        lon:
            Longitude in decimal degrees (WGS-84).
        buffer_m:
            Half-side of the square box in metres.

        Returns
        -------
        Tuple ``(west, south, east, north)`` in EPSG:3857 metres.
        """
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        cx, cy = transformer.transform(lon, lat)
        return (cx - buffer_m, cy - buffer_m, cx + buffer_m, cy + buffer_m)
