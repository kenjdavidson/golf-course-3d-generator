"""
``generate`` command – produce a 3D model for a single par-3 hole from
a local DTM tile directory.

Elevation data is read from a directory of DTM/DEM tile files (e.g.
``.img`` or ``.tif``) that are automatically indexed into a GDAL Virtual
Raster (``index.vrt``).

**With an OSM hole ID** – the hole outline is fetched from OpenStreetMap
and used to clip the raster to the exact hole boundary::

    python -m src.main generate \\
        --dtm-dir /data/milton \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers \\
        --z-scale 1.5 \\
        --target-size 200

**Without an OSM hole ID** – the coordinate + buffer bounding box is used
directly, and features (greens, bunkers) are detected automatically using
the Laplacian of Gaussian (LoG) filter::

    python -m src.main generate \\
        --dtm-dir /data/milton \\
        --lat 43.5123 --lon -79.8765 \\
        --buffer 150 \\
        --output /output/hole3_layers

Find the OSM hole ID by:

1. Visiting https://www.openstreetmap.org/ and navigating to the course.
2. Clicking the *Query features* tool and clicking on the hole outline.
3. Noting the **Way ID** shown in the panel (e.g. ``123456789``).

Inside Docker::

    docker compose run --rm generator generate \\
        --dtm-dir /data/milton \\
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
        required=False,
        default=None,
        type=int,
        help=(
            "OpenStreetMap way ID of the golf hole (golf=hole way).  "
            "When supplied, the hole outline clips the elevation raster to the "
            "exact hole boundary.  When omitted, the coordinate + --buffer area "
            "is used directly and features are detected automatically."
        ),
    )
    @click.option(
        "--buffer",
        default=50,
        show_default=True,
        type=float,
        help=(
            "Buffer (metres) added around the hole boundary before clipping.  "
            "Also used as the study-area half-width when --hole-id is omitted."
        ),
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

        When ``--hole-id`` is supplied the OSM hole outline clips the elevation
        raster to the exact hole boundary.  When omitted, the ``--lat``/``--lon``
        + ``--buffer`` bounding box is used and features (greens, bunkers) are
        detected automatically from the elevation data.

        Outputs three STL files (base_terrain, green_inlay, bunker_cutout)
        for multi-material 3D printing.

        For cloud-based elevation (no local files), use ``generate-api``.
        """
        geometry = None
        label = f"lat={lat},lon={lon}"

        if hole_id is not None:
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
