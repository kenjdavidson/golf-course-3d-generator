"""
Tests for OntarioGeohubClient.

All HTTP calls are mocked – no network access required.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from unittest.mock import MagicMock, patch

from src.services.ontario_geohub import OntarioGeohubClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tiff_bytes(
    elevation: np.ndarray | None = None,
    west: float = -8890000.0,
    south: float = 5450000.0,
    east: float = -8890000.0 + 300.0,
    north: float = 5450000.0 + 300.0,
) -> bytes:
    """Return raw GeoTIFF bytes (EPSG:3857, 32-bit float) for use as mock response."""
    if elevation is None:
        elevation = np.ones((16, 16), dtype=np.float32) * 100.0

    rows, cols = elevation.shape
    transform = from_bounds(west, south, east, north, cols, rows)

    fd, path = tempfile.mkstemp(suffix=".tif")
    try:
        os.close(fd)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=rows,
            width=cols,
            count=1,
            dtype=np.float32,
            crs="EPSG:3857",
            transform=transform,
        ) as ds:
            ds.write(elevation, 1)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOntarioGeohubClientBbox:
    def test_bbox_is_centred_on_coordinate(self):
        w, s, e, n = OntarioGeohubClient._compute_bbox_3857(
            lat=43.5, lon=-79.8, buffer_m=150.0
        )
        cx = (w + e) / 2
        cy = (s + n) / 2
        # Width and height should both be 2 * buffer
        assert abs((e - w) - 300.0) < 1.0
        assert abs((n - s) - 300.0) < 1.0

    def test_bbox_east_greater_than_west(self):
        w, s, e, n = OntarioGeohubClient._compute_bbox_3857(
            lat=43.5, lon=-79.8, buffer_m=100.0
        )
        assert e > w

    def test_bbox_north_greater_than_south(self):
        w, s, e, n = OntarioGeohubClient._compute_bbox_3857(
            lat=43.5, lon=-79.8, buffer_m=100.0
        )
        assert n > s

    def test_bbox_size_scales_with_buffer(self):
        w1, s1, e1, n1 = OntarioGeohubClient._compute_bbox_3857(
            lat=43.5, lon=-79.8, buffer_m=50.0
        )
        w2, s2, e2, n2 = OntarioGeohubClient._compute_bbox_3857(
            lat=43.5, lon=-79.8, buffer_m=200.0
        )
        assert (e2 - w2) > (e1 - w1)


class TestOntarioGeohubClientFetch:
    def test_fetch_writes_temp_file(self):
        """fetch_elevation_tiff should return a path to an existing file."""
        mock_response = MagicMock()
        mock_response.content = _make_tiff_bytes()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.ontario_geohub.requests.get", return_value=mock_response):
            client = OntarioGeohubClient()
            path = client.fetch_elevation_tiff(lat=43.5, lon=-79.8, buffer_m=150.0)

        try:
            assert os.path.isfile(path)
            assert path.endswith(".tif")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_fetch_sends_correct_params(self):
        """The GET request should include bbox, pixelType=F32, format=tiff."""
        mock_response = MagicMock()
        mock_response.content = _make_tiff_bytes()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.ontario_geohub.requests.get", return_value=mock_response) as mock_get:
            client = OntarioGeohubClient()
            client.fetch_elevation_tiff(lat=43.5, lon=-79.8, buffer_m=150.0)

        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert "bbox" in params
        assert params.get("pixelType") == "F32"
        assert params.get("format") == "tiff"
        assert params.get("f") == "image"

    def test_fetch_raises_on_http_error(self):
        """HTTP errors from the server should propagate as requests.HTTPError."""
        import requests as req_module

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req_module.HTTPError("404")

        with patch("src.services.ontario_geohub.requests.get", return_value=mock_response):
            client = OntarioGeohubClient()
            with pytest.raises(req_module.HTTPError):
                client.fetch_elevation_tiff(lat=43.5, lon=-79.8, buffer_m=150.0)

    def test_fetch_cleans_up_temp_file_on_write_error(self):
        """Temp file should be deleted if writing the response body fails."""
        mock_response = MagicMock()
        mock_response.content = _make_tiff_bytes()
        mock_response.raise_for_status = MagicMock()

        created_paths: list[str] = []

        original_open = open

        def patched_open(path, mode="r", *args, **kwargs):
            if "wb" in mode and path.endswith(".tif"):
                created_paths.append(path)
                raise OSError("disk full")
            return original_open(path, mode, *args, **kwargs)

        with patch("src.services.ontario_geohub.requests.get", return_value=mock_response):
            with patch("builtins.open", side_effect=patched_open):
                client = OntarioGeohubClient()
                with pytest.raises(OSError):
                    client.fetch_elevation_tiff(lat=43.5, lon=-79.8, buffer_m=150.0)

        # The temp file should have been removed.
        for p in created_paths:
            assert not os.path.exists(p), f"Temp file was not cleaned up: {p}"

    def test_fetch_uses_custom_base_url(self):
        """Client should use the base_url passed at construction time."""
        custom_url = "https://example.com/custom/ImageServer/exportImage"
        mock_response = MagicMock()
        mock_response.content = _make_tiff_bytes()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.ontario_geohub.requests.get", return_value=mock_response) as mock_get:
            client = OntarioGeohubClient(base_url=custom_url)
            path = client.fetch_elevation_tiff(lat=43.5, lon=-79.8, buffer_m=150.0)
            os.unlink(path)

        args, _ = mock_get.call_args
        assert args[0] == custom_url

    def test_image_size_param_matches_constructor(self):
        """The size parameter sent to the server should reflect image_size."""
        mock_response = MagicMock()
        mock_response.content = _make_tiff_bytes()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.ontario_geohub.requests.get", return_value=mock_response) as mock_get:
            client = OntarioGeohubClient(image_size=256)
            path = client.fetch_elevation_tiff(lat=43.5, lon=-79.8, buffer_m=150.0)
            os.unlink(path)

        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["size"] == "256,256"
