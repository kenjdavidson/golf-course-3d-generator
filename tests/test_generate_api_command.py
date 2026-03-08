"""
Tests for the generate-api CLI command.

Covers option parsing, default values, error handling when the OSM way
is not found, and correct delegation to ImageServerHoleGenerator.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

def _make_mock_generator(tmp_path):
    """Return a mock ImageServerHoleGenerator that writes placeholder STL files."""
    mock_gen = MagicMock()

    def fake_generate(**kwargs):
        out = kwargs.get("output_path", str(tmp_path / "out"))
        os.makedirs(out, exist_ok=True)
        for name in ("base_terrain", "green_inlay", "bunker_cutout"):
            with open(os.path.join(out, f"{name}.stl"), "wb"):
                pass

    mock_gen.generate.side_effect = fake_generate
    return mock_gen


# ---------------------------------------------------------------------------
# Option parsing
# ---------------------------------------------------------------------------

class TestGenerateApiOptions:
    def test_requires_lat(self):
        result = CliRunner().invoke(cli, ["generate-api", "--lon", "-79.8"])
        assert result.exit_code != 0
        assert "lat" in result.output.lower() or "missing" in result.output.lower()

    def test_requires_lon(self):
        result = CliRunner().invoke(cli, ["generate-api", "--lat", "43.5"])
        assert result.exit_code != 0
        assert "lon" in result.output.lower() or "missing" in result.output.lower()

    def test_buffer_default_is_150(self):
        """generate-api default --buffer should be 150 (fetch half-width)."""
        result = CliRunner().invoke(cli, ["generate-api", "--help"])
        assert "150" in result.output

    def test_hole_id_is_optional(self):
        """generate-api --hole-id should not appear as [required] in help."""
        result = CliRunner().invoke(cli, ["generate-api", "--help"])
        # The option should exist but not be marked required
        assert "--hole-id" in result.output
        assert "[required]" not in result.output.split("--hole-id")[1].split("\n")[0]

    def test_no_dtm_dir_option(self):
        """generate-api should NOT expose a --dtm-dir option."""
        result = CliRunner().invoke(cli, ["generate-api", "--help"])
        assert "--dtm-dir" not in result.output


# ---------------------------------------------------------------------------
# Delegation to ImageServerHoleGenerator
# ---------------------------------------------------------------------------

class TestGenerateApiDelegation:
    def test_delegates_to_imageserver_generator(self, tmp_path):
        """generate-api must instantiate ImageServerHoleGenerator, not VRTHoleGenerator."""
        with patch(
            "src.commands.generate_api.ImageServerHoleGenerator"
        ) as MockGen:
            MockGen.return_value = _make_mock_generator(tmp_path)

            result = CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        MockGen.assert_called_once()
        MockGen.return_value.generate.assert_called_once()

    def test_passes_lat_lon_to_generator(self, tmp_path):
        with patch(
            "src.commands.generate_api.ImageServerHoleGenerator"
        ) as MockGen:
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance

            CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--lat", "43.5123",
                    "--lon", "-79.8765",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        call_kwargs = mock_instance.generate.call_args.kwargs
        assert call_kwargs["lat"] == pytest.approx(43.5123)
        assert call_kwargs["lon"] == pytest.approx(-79.8765)

    def test_passes_custom_buffer(self, tmp_path):
        with patch(
            "src.commands.generate_api.ImageServerHoleGenerator"
        ) as MockGen:
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance

            CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--buffer", "200",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        call_kwargs = mock_instance.generate.call_args.kwargs
        assert call_kwargs["buffer_m"] == pytest.approx(200.0)

    def test_passes_print_options_to_constructor(self, tmp_path):
        with patch(
            "src.commands.generate_api.ImageServerHoleGenerator"
        ) as MockGen:
            MockGen.return_value = _make_mock_generator(tmp_path)

            CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--base-thickness", "5.0",
                    "--z-scale", "2.0",
                    "--target-size", "150",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        MockGen.assert_called_once_with(
            base_thickness=pytest.approx(5.0),
            z_scale=pytest.approx(2.0),
            target_size_mm=pytest.approx(150.0),
        )


# ---------------------------------------------------------------------------
# Optional --hole-id handling
# ---------------------------------------------------------------------------

class TestGenerateApiHoleId:
    def test_without_hole_id_passes_none_geometry(self, tmp_path):
        with patch(
            "src.commands.generate_api.ImageServerHoleGenerator"
        ) as MockGen:
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance

            CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        call_kwargs = mock_instance.generate.call_args.kwargs
        assert call_kwargs["geometry"] is None

    def test_with_hole_id_fetches_and_passes_geometry(self, tmp_path):
        from shapely.geometry import box

        fake_geom = box(-79.89, 43.50, -79.87, 43.52)

        with (
            patch("src.commands.generate_api.ImageServerHoleGenerator") as MockGen,
            patch("src.commands.generate_api.CourseFetcher") as MockFetcher,
        ):
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance
            MockFetcher.return_value.fetch_hole_by_id.return_value = fake_geom

            CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--hole-id", "123456789",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        call_kwargs = mock_instance.generate.call_args.kwargs
        assert call_kwargs["geometry"] is fake_geom

    def test_with_invalid_hole_id_exits_with_error(self, tmp_path):
        with patch("src.commands.generate_api.CourseFetcher") as MockFetcher:
            MockFetcher.return_value.fetch_hole_by_id.return_value = None

            result = CliRunner().invoke(
                cli,
                [
                    "generate-api",
                    "--hole-id", "999",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
            )

        assert result.exit_code != 0
