"""
Tests for CourseFetcher.

Network calls to the Overpass API are mocked so tests run offline.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import Polygon

from src.course_fetcher import CourseFetcher


# ---------------------------------------------------------------------------
# Helpers to build fake overpy objects
# ---------------------------------------------------------------------------

def _make_node(lon: float, lat: float) -> MagicMock:
    node = MagicMock()
    node.lon = lon
    node.lat = lat
    return node


def _make_way(osm_id: int, node_coords, tags=None) -> MagicMock:
    way = MagicMock()
    way.id = osm_id
    way.tags = tags or {}
    way.nodes = [_make_node(lon, lat) for lon, lat in node_coords]
    return way


def _square_coords(cx: float, cy: float, half: float = 0.001):
    """Return 4 corner coordinates forming a small square around (cx, cy)."""
    return [
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    ]


# ---------------------------------------------------------------------------
# Tests for fetch_hole_by_id
# ---------------------------------------------------------------------------

class TestFetchHoleById:
    @patch("src.course_fetcher.overpy.Overpass")
    def test_returns_polygon_for_valid_way(self, MockOverpass):
        coords = _square_coords(-74.005, 40.705)
        mock_way = _make_way(12345, coords, tags={"golf": "hole", "par": "3"})

        mock_result = MagicMock()
        mock_result.ways = [mock_way]
        MockOverpass.return_value.query.return_value = mock_result

        fetcher = CourseFetcher()
        poly = fetcher.fetch_hole_by_id(12345)

        assert poly is not None
        assert isinstance(poly, Polygon)
        assert poly.is_valid

    @patch("src.course_fetcher.overpy.Overpass")
    def test_returns_none_when_no_ways(self, MockOverpass):
        mock_result = MagicMock()
        mock_result.ways = []
        MockOverpass.return_value.query.return_value = mock_result

        fetcher = CourseFetcher()
        poly = fetcher.fetch_hole_by_id(99999)

        assert poly is None

    @patch("src.course_fetcher.overpy.Overpass")
    def test_closes_open_ring(self, MockOverpass):
        # Provide open (not closed) ring
        coords = _square_coords(-74.005, 40.705)  # 4 points, not closed
        mock_way = _make_way(1, coords)
        mock_result = MagicMock()
        mock_result.ways = [mock_way]
        MockOverpass.return_value.query.return_value = mock_result

        fetcher = CourseFetcher()
        poly = fetcher.fetch_hole_by_id(1)

        assert poly is not None
        exterior_coords = list(poly.exterior.coords)
        assert exterior_coords[0] == exterior_coords[-1], "Ring should be closed"


# ---------------------------------------------------------------------------
# Tests for fetch_par3_holes_near
# ---------------------------------------------------------------------------

class TestFetchPar3HolesNear:
    @patch("src.course_fetcher.overpy.Overpass")
    def test_returns_list_of_hole_dicts(self, MockOverpass):
        coords_a = _square_coords(-74.005, 40.705)
        coords_b = _square_coords(-74.010, 40.710)
        way_a = _make_way(1, coords_a, {"golf": "hole", "par": "3", "ref": "3", "name": "Hole 3"})
        way_b = _make_way(2, coords_b, {"golf": "hole", "par": "3", "ref": "7"})

        mock_result = MagicMock()
        mock_result.ways = [way_a, way_b]
        MockOverpass.return_value.query.return_value = mock_result

        fetcher = CourseFetcher()
        holes = fetcher.fetch_par3_holes_near(40.705, -74.005)

        assert len(holes) == 2
        assert holes[0]["osm_id"] == 1
        assert holes[0]["ref"] == "3"
        assert holes[0]["name"] == "Hole 3"
        assert isinstance(holes[0]["geometry"], Polygon)

    @patch("src.course_fetcher.overpy.Overpass")
    def test_empty_result_returns_empty_list(self, MockOverpass):
        mock_result = MagicMock()
        mock_result.ways = []
        MockOverpass.return_value.query.return_value = mock_result

        fetcher = CourseFetcher()
        holes = fetcher.fetch_par3_holes_near(40.705, -74.005)

        assert holes == []

    @patch("src.course_fetcher.overpy.Overpass")
    def test_ways_with_too_few_nodes_are_skipped(self, MockOverpass):
        bad_way = _make_way(99, [(0.0, 0.0), (1.0, 1.0)])  # only 2 nodes
        good_way = _make_way(100, _square_coords(0.0, 0.0))

        mock_result = MagicMock()
        mock_result.ways = [bad_way, good_way]
        MockOverpass.return_value.query.return_value = mock_result

        fetcher = CourseFetcher()
        holes = fetcher.fetch_par3_holes_near(0.0, 0.0)

        assert len(holes) == 1
        assert holes[0]["osm_id"] == 100


# ---------------------------------------------------------------------------
# Tests for _way_to_polygon (unit tests on the static helper)
# ---------------------------------------------------------------------------

class TestWayToPolygon:
    def test_valid_way_returns_polygon(self):
        coords = _square_coords(0.0, 0.0)
        way = _make_way(1, coords)
        poly = CourseFetcher._way_to_polygon(way)
        assert poly is not None
        assert isinstance(poly, Polygon)

    def test_too_few_nodes_returns_none(self):
        way = _make_way(1, [(0.0, 0.0), (1.0, 0.0)])
        result = CourseFetcher._way_to_polygon(way)
        assert result is None

    def test_already_closed_ring_stays_closed(self):
        coords = _square_coords(0.0, 0.0)
        closed = coords + [coords[0]]  # manually close
        way = _make_way(1, closed)
        poly = CourseFetcher._way_to_polygon(way)
        assert poly is not None
        assert poly.is_valid
