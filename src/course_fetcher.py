"""
OpenStreetMap golf course data fetcher.

Uses the Overpass API to retrieve golf hole geometries (ways tagged
``golf=hole``) for a given location or OSM object ID.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import overpy
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Overpass query templates
# ---------------------------------------------------------------------------

_QUERY_BY_HOLE_ID = """
[out:json][timeout:30];
way({hole_id});
out body;
>;
out skel qt;
"""

_QUERY_BY_LOCATION = """
[out:json][timeout:60];
(
  way[golf=hole][par={par}](around:{radius},{lat},{lon});
);
out body;
>;
out skel qt;
"""

_QUERY_COURSE_HOLES = """
[out:json][timeout:60];
(
  relation[leisure=golf_course](around:{radius},{lat},{lon});
  way[leisure=golf_course](around:{radius},{lat},{lon});
);
out body;
>;
out skel qt;
"""


class CourseFetcher:
    """Fetch golf hole geometry from OpenStreetMap via the Overpass API."""

    def __init__(self, overpass_url: str = "https://overpass-api.de/api/interpreter") -> None:
        self._api = overpy.Overpass(url=overpass_url)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_hole_by_id(self, osm_way_id: int) -> Optional[Polygon]:
        """Return the polygon for a single OSM way (golf hole).

        Parameters
        ----------
        osm_way_id:
            The OpenStreetMap way ID for the ``golf=hole`` way.

        Returns
        -------
        Shapely ``Polygon`` in WGS-84 (lon/lat) or ``None`` if not found.
        """
        result = self._api.query(_QUERY_BY_HOLE_ID.format(hole_id=osm_way_id))
        ways = result.ways
        if not ways:
            return None
        return self._way_to_polygon(ways[0])

    def fetch_par3_holes_near(
        self,
        lat: float,
        lon: float,
        radius_m: float = 5000,
    ) -> List[Dict]:
        """Return all par-3 golf holes within *radius_m* metres of (lat, lon).

        Each entry in the returned list contains:
        - ``osm_id`` (int)
        - ``name`` (str, may be empty)
        - ``ref`` (str – hole number, may be empty)
        - ``geometry`` (Shapely ``Polygon`` in WGS-84)
        - ``tags`` (dict)
        """
        query = _QUERY_BY_LOCATION.format(
            par=3, radius=int(radius_m), lat=lat, lon=lon
        )
        result = self._api.query(query)
        holes = []
        for way in result.ways:
            poly = self._way_to_polygon(way)
            if poly is None:
                continue
            holes.append(
                {
                    "osm_id": way.id,
                    "name": way.tags.get("name", ""),
                    "ref": way.tags.get("ref", ""),
                    "geometry": poly,
                    "tags": dict(way.tags),
                }
            )
        return holes

    def fetch_course_boundary(
        self,
        lat: float,
        lon: float,
        radius_m: float = 1000,
    ) -> Optional[Polygon]:
        """Return the outer boundary polygon of the nearest golf course.

        Parameters
        ----------
        lat, lon:
            Approximate centre of the golf course (WGS-84 degrees).
        radius_m:
            Search radius in metres.

        Returns
        -------
        Shapely ``Polygon`` / ``MultiPolygon`` or ``None``.
        """
        query = _QUERY_COURSE_HOLES.format(
            radius=int(radius_m), lat=lat, lon=lon
        )
        result = self._api.query(query)

        polygons = []
        for way in result.ways:
            poly = self._way_to_polygon(way)
            if poly is not None:
                polygons.append(poly)

        if not polygons:
            return None

        merged = unary_union(polygons)
        if isinstance(merged, (Polygon, MultiPolygon)):
            return merged
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _way_to_polygon(way: overpy.Way) -> Optional[Polygon]:
        """Convert an Overpass *Way* to a Shapely polygon (lon/lat).

        Returns ``None`` if the way has fewer than 3 resolved nodes.
        """
        coords = []
        for node in way.nodes:
            coords.append((float(node.lon), float(node.lat)))

        if len(coords) < 3:
            return None

        # Close the ring if necessary
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        try:
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
            return poly
        except Exception:
            return None
