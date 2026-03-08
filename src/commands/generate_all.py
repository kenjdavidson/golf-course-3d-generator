"""
``generate-all`` command – produce 3D models for every par-3 hole near a
given coordinate, from a local DTM tile directory.

OpenStreetMap is queried for all ways tagged ``golf=hole`` + ``par=3``
within the specified search radius.  Elevation data is read from a local
directory of DTM/DEM tile files (e.g. ``.img`` or ``.tif``) that are
automatically indexed into a GDAL Virtual Raster (``index.vrt``).

A separate output directory containing three STL files is produced for
each hole found.

Usage::

    python -m src.main generate-all \\
        --dtm-dir /data/milton \\
        --lat 43.5123 --lon -79.8765 \\
        --radius 3000 \\
        --output-dir /output \\
        --z-scale 1.5

Inside Docker::

    docker compose run --rm generator generate-all \\
        --dtm-dir /data/milton \\
        --lat 43.5123 --lon -79.8765 \\
        --radius 5000 \\
        --output-dir /output

To generate models without local files, see the ``generate-api`` command.
"""

from __future__ import annotations

import sys

import click

from src.commands.options import coordinate_options, dtm_dir_option, print_options
from src.course_fetcher import CourseFetcher
from src.generators.vrt_generator import VRTHoleGenerator


def register(cli: click.Group) -> None:
    """Attach the ``generate-all`` command to *cli*."""

    @cli.command(name="generate-all")
    @dtm_dir_option
    @coordinate_options
    @print_options
    @click.option(
        "--radius",
        default=5000,
        show_default=True,
        type=float,
        help="Search radius in metres around --lat/--lon.",
    )
    @click.option(
        "--buffer",
        default=50,
        show_default=True,
        type=float,
        help="Buffer (metres) to add around each hole boundary before clipping the DTM.",
    )
    @click.option(
        "--output-dir",
        default="output",
        show_default=True,
        type=click.Path(),
        help=(
            "Directory in which to write per-hole output subdirectories, "
            "each containing three STL files."
        ),
    )
    def generate_all(
        dtm_dir,
        lat,
        lon,
        radius,
        buffer,
        base_thickness,
        z_scale,
        target_size,
        output_dir,
    ):
        """Find all par-3 holes near LAT/LON and generate a 3D model for each.

        Uses a local DTM tile directory for elevation data.  Each hole produces
        a subdirectory inside OUTPUT_DIR containing three STL files
        (base_terrain, green_inlay, bunker_cutout) for multi-material 3D printing.

        For cloud-based elevation (no local files), use ``generate-api`` per hole.
        """
        click.echo(f"Searching for par-3 holes within {radius} m of ({lat}, {lon}) …")
        fetcher = CourseFetcher()
        holes = fetcher.fetch_par3_holes_near(lat, lon, radius_m=radius)

        if not holes:
            click.echo("No par-3 holes found in the search area.")
            sys.exit(0)

        click.echo(f"Found {len(holes)} par-3 hole(s).")

        # Single generator instance shared across all holes (VRT is opened once per hole).
        generator = VRTHoleGenerator(
            dtm_dir=dtm_dir,
            base_thickness=base_thickness,
            z_scale=z_scale,
            target_size_mm=target_size,
        )

        for hole in holes:
            osm_id = hole["osm_id"]
            ref = hole.get("ref", "")
            name = hole.get("name", "")
            label = f"hole-{ref}" if ref else f"osm-{osm_id}"
            output_path = f"{output_dir}/{label}"

            # Derive study-area centre from the hole's own geometry centroid.
            centroid = hole["geometry"].centroid
            hole_lat, hole_lon = centroid.y, centroid.x

            click.echo(
                f"  Processing {label} (OSM {osm_id})"
                + (f" – {name}" if name else "")
            )
            try:
                generator.generate(
                    lat=hole_lat,
                    lon=hole_lon,
                    buffer_m=buffer,
                    output_path=output_path,
                    label=label,
                    geometry=hole["geometry"],
                )
            except Exception as exc:  # noqa: BLE001
                click.echo(
                    f"    WARNING: Failed to generate {label}: {exc}", err=True
                )
