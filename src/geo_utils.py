"""Shared geographic utility functions.

These helpers are used by pipeline stages and generator implementations
to perform coordinate reprojection and study-area derivation.
"""

from __future__ import annotations

from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

# Half-width in metres of the study-area bounding box when --lat/--lon are
# used with --dtm-dir.  A 100 m radius gives a ≈200 m × 200 m square.
_STUDY_AREA_RADIUS_M = 100


def buffer_wgs84_geometry(geometry: BaseGeometry, buffer_m: float) -> BaseGeometry:
    """Return *geometry* buffered by *buffer_m* metres using a UTM projection.

    The geometry is temporarily reprojected to a locally appropriate UTM zone
    (derived from its centroid), buffered there in metres, then projected back
    to WGS-84 (EPSG:4326).  This avoids the latitude-dependent inaccuracy of a
    simple degree-based buffer.

    Parameters
    ----------
    geometry:
        Input Shapely geometry in WGS-84 (EPSG:4326).
    buffer_m:
        Buffer radius in metres.

    Returns
    -------
    Buffered geometry in WGS-84.
    """
    centroid = geometry.centroid
    lon, lat = centroid.x, centroid.y
    utm_zone = int((lon + 180) / 6) + 1
    hemisphere = "north" if lat >= 0 else "south"
    utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

    to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

    geom_utm = shapely_transform(to_utm.transform, geometry)
    buffered_utm = geom_utm.buffer(buffer_m)
    return shapely_transform(to_wgs84.transform, buffered_utm)


def coordinate_to_study_area(lat: float, lon: float) -> BaseGeometry:
    """Return a ~200 m × 200 m WGS-84 bounding box centred on *lat* / *lon*.

    The box is derived by buffering the coordinate point by
    :data:`_STUDY_AREA_RADIUS_M` metres in UTM space and taking the
    rectangular envelope of the resulting circle.

    Parameters
    ----------
    lat:
        Latitude in decimal degrees (WGS-84).
    lon:
        Longitude in decimal degrees (WGS-84).

    Returns
    -------
    Shapely geometry in WGS-84 that covers the study area.
    """
    centre = Point(lon, lat)
    buffered = buffer_wgs84_geometry(centre, _STUDY_AREA_RADIUS_M)
    return buffered.envelope
