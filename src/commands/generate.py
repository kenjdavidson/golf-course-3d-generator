"""
``generate`` command – produce a 3D model for a single par-3 hole from
a local DTM tile directory.

Elevation data is read from a directory of DTM/DEM tile files (e.g.
``.img`` or ``.tif``) that are automatically indexed into a GDAL Virtual
Raster (``index.vrt``).  The hole outline is fetched from OpenStreetMap
by way ID and used to clip the raster to the exact hole boundary.

Find the OSM hole ID by:

1. Visiting https://www.openstreetmap.org/ and navigating to the course.
2. Clicking the *Query features* tool and clicking on the hole outline.
3. Noting the **Way ID** shown in the panel (e.g. ``123456789``).

Usage::

    python -m src.main generate \\
        --dtm-dir /data/milton \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers \\
        --z-scale 1.5 \\
        --target-size 200

Inside Docker::

    docker compose run --rm generator generate \\
        --dtm-dir /data/milton \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers

The output is a directory (or ``.zip`` if the path ends in ``.zip``)
containing three STL files for multi-material / filament-swap printing:

* ``base_terrain.stl`` – full terrain surface (structural body)
* ``green_inlay.stl``  – flat elevated plateaus (greens / tee colours)
* ``bunker_cutout.stl``– depression areas (sand / bunker filament)

To generate a model without local files, see the ``generate-api`` command.
"""

from __future__ import annotations

import sys

import click

from src.commands.options import coordinate_options, dtm_dir_option, print_options
from src.course_fetcher import CourseFetcher
from src.generators.vrt_generator import VRTHoleGenerator


def register(cli: click.Group) -> None:
    """Attach the ``generate`` command to *cli*."""

    @cli.command()
    @dtm_dir_option
    @coordinate_options
    @print_options
    @click.option(
        "--hole-id",
        required=True,
        type=int,
        help=(
            "OpenStreetMap way ID of the golf hole (golf=hole way).  "
            "Used to fetch the hole outline and clip the elevation raster."
        ),
    )
    @click.option(
        "--buffer",
        default=50,
        show_default=True,
        type=float,
        help="Buffer (metres) to add around the hole boundary before clipping the DTM.",
    )
    @click.option(
        "--output",
        default="hole_layers",
        show_default=True,
        type=click.Path(),
        help=(
            "Output path: a directory that will contain the three layer STLs, "
            "or a path ending in .zip to receive a single archive."
        ),
    )
    def generate(
        dtm_dir,
        lat,
        lon,
        hole_id,
        buffer,
        base_thickness,
        z_scale,
        target_size,
        output,
    ):
        """Generate a 3D model for a single par-3 hole from local DTM files.

        Fetches the OSM hole outline, clips the local elevation raster to it,
        and outputs three STL files (base_terrain, green_inlay, bunker_cutout)
        for multi-material 3D printing.

        For cloud-based elevation (no local files), use ``generate-api``.
        """
        click.echo(f"Fetching hole geometry for OSM way {hole_id} …")
        fetcher = CourseFetcher()
        geometry = fetcher.fetch_hole_by_id(hole_id)
        if geometry is None:
            click.echo(f"ERROR: Could not find OSM way {hole_id}.", err=True)
            sys.exit(1)
        label = f"OSM way {hole_id}"

        generator = VRTHoleGenerator(
            dtm_dir=dtm_dir,
            base_thickness=base_thickness,
            z_scale=z_scale,
            target_size_mm=target_size,
        )
        generator.generate(
            lat=lat,
            lon=lon,
            buffer_m=buffer,
            output_path=output,
            label=label,
            geometry=geometry,
        )
