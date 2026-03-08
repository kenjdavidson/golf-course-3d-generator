"""
Tests for the generate CLI command (local VRT path).

Covers option parsing, default values, both code paths (with and without
--hole-id), and correct delegation to VRTHoleGenerator.
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
    """Return a mock VRTHoleGenerator that writes placeholder STL files."""
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

class TestGenerateOptions:
    def test_requires_dtm_dir(self, tmp_path):
        result = CliRunner().invoke(
            cli,
            ["generate", "--lat", "43.5", "--lon", "-79.8"],
        )
        assert result.exit_code != 0
        assert "dtm-dir" in result.output.lower() or "missing" in result.output.lower()

    def test_requires_lat(self, tmp_path):
        result = CliRunner().invoke(
            cli,
            ["generate", "--dtm-dir", str(tmp_path), "--lon", "-79.8"],
        )
        assert result.exit_code != 0

    def test_requires_lon(self, tmp_path):
        result = CliRunner().invoke(
            cli,
            ["generate", "--dtm-dir", str(tmp_path), "--lat", "43.5"],
        )
        assert result.exit_code != 0

    def test_hole_id_is_optional(self):
        """--hole-id must NOT be marked [required] in help."""
        result = CliRunner().invoke(cli, ["generate", "--help"])
        assert "--hole-id" in result.output
        assert "[required]" not in result.output.split("--hole-id")[1].split("\n")[0]

    def test_buffer_default_is_50(self):
        result = CliRunner().invoke(cli, ["generate", "--help"])
        assert "50" in result.output




# ---------------------------------------------------------------------------
# Without --hole-id: coordinate + buffer path
# ---------------------------------------------------------------------------

class TestGenerateWithoutHoleId:
    def test_passes_none_geometry_when_no_hole_id(self, tmp_path):
        with patch("src.commands.generate.VRTHoleGenerator") as MockGen:
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance

            result = CliRunner().invoke(
                cli,
                [
                    "generate",
                    "--dtm-dir", str(tmp_path),
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_instance.generate.call_args.kwargs
        assert call_kwargs["geometry"] is None

    def test_label_uses_coordinates_when_no_hole_id(self, tmp_path):
        with patch("src.commands.generate.VRTHoleGenerator") as MockGen:
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance

            CliRunner().invoke(
                cli,
                [
                    "generate",
                    "--dtm-dir", str(tmp_path),
                    "--lat", "43.5123",
                    "--lon", "-79.8765",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        call_kwargs = mock_instance.generate.call_args.kwargs
        assert "43.5123" in call_kwargs["label"]
        assert "-79.8765" in call_kwargs["label"]


# ---------------------------------------------------------------------------
# With --hole-id: OSM outline path
# ---------------------------------------------------------------------------

class TestGenerateWithHoleId:
    def test_fetches_geometry_and_passes_it(self, tmp_path):
        from shapely.geometry import box

        fake_geom = box(-79.89, 43.50, -79.87, 43.52)

        with (
            patch("src.commands.generate.VRTHoleGenerator") as MockGen,
            patch("src.commands.generate.CourseFetcher") as MockFetcher,
        ):
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance
            MockFetcher.return_value.fetch_hole_by_id.return_value = fake_geom

            result = CliRunner().invoke(
                cli,
                [
                    "generate",
                    "--dtm-dir", str(tmp_path),
                    "--hole-id", "123456789",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_instance.generate.call_args.kwargs
        assert call_kwargs["geometry"] is fake_geom

    def test_label_uses_osm_id_when_hole_id_given(self, tmp_path):
        from shapely.geometry import box

        fake_geom = box(-79.89, 43.50, -79.87, 43.52)

        with (
            patch("src.commands.generate.VRTHoleGenerator") as MockGen,
            patch("src.commands.generate.CourseFetcher") as MockFetcher,
        ):
            mock_instance = _make_mock_generator(tmp_path)
            MockGen.return_value = mock_instance
            MockFetcher.return_value.fetch_hole_by_id.return_value = fake_geom

            CliRunner().invoke(
                cli,
                [
                    "generate",
                    "--dtm-dir", str(tmp_path),
                    "--hole-id", "123456789",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        call_kwargs = mock_instance.generate.call_args.kwargs
        assert "123456789" in call_kwargs["label"]

    def test_exits_with_error_for_invalid_hole_id(self, tmp_path):
        with patch("src.commands.generate.CourseFetcher") as MockFetcher:
            MockFetcher.return_value.fetch_hole_by_id.return_value = None

            result = CliRunner().invoke(
                cli,
                [
                    "generate",
                    "--dtm-dir", str(tmp_path),
                    "--hole-id", "999",
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--output", str(tmp_path / "out"),
                ],
            )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Print options propagated to constructor
# ---------------------------------------------------------------------------

class TestGeneratePrintOptions:
    def test_print_options_passed_to_constructor(self, tmp_path):
        with patch("src.commands.generate.VRTHoleGenerator") as MockGen:
            MockGen.return_value = _make_mock_generator(tmp_path)

            CliRunner().invoke(
                cli,
                [
                    "generate",
                    "--dtm-dir", str(tmp_path),
                    "--lat", "43.5",
                    "--lon", "-79.8",
                    "--base-thickness", "4.0",
                    "--z-scale", "2.0",
                    "--target-size", "200",
                    "--output", str(tmp_path / "out"),
                ],
                catch_exceptions=False,
            )

        MockGen.assert_called_once_with(
            dtm_dir=str(tmp_path),
            base_thickness=pytest.approx(4.0),
            z_scale=pytest.approx(2.0),
            target_size_mm=pytest.approx(200.0),
        )
