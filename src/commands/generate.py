"""
``generate`` command – produce a 3D model for a single par-3 hole.

The hole is identified by its OpenStreetMap way ID.  Find the ID by:

1. Visiting https://www.openstreetmap.org/ and navigating to the course.
2. Clicking the *Query features* tool and clicking on the hole outline.
3. Noting the **Way ID** shown in the panel (e.g. ``123456789``).

Single-file mode (original)
---------------------------
::

    python -m src.main generate \\
        --dtm /data/terrain.tif \\
        --hole-id 123456789 \\
        --output /output/hole3.stl \\
        --z-scale 1.5 \\
        --target-size 200

Multi-tile directory mode (Ontario Milton dataset, etc.)
--------------------------------------------------------
Pass a directory of ``.img`` tiles instead of a single file.  An
``index.vrt`` is built automatically if absent.  Supply the coordinates
of the study area centre; a 200 m × 200 m region is extracted::

    python -m src.main generate \\
        --dtm-dir /data/milton \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers

The output will be a directory (or ``.zip`` if the path ends in ``.zip``)
containing three STL files:

* ``base_terrain.stl`` – full terrain surface (structural body)
* ``green_inlay.stl``  – flat elevated plateaus (greens / tee colours)
* ``bunker_cutout.stl``– depression areas (sand / bunker filament)

Inside Docker::

    docker compose run --rm generator generate \\
        --dtm-dir /data/milton \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers
"""

from __future__ import annotations

import sys

import click

from src.commands.options import (
    coordinate_options,
    dtm_dir_option,
    dtm_option,
    mesh_options,
)
from src.course_fetcher import CourseFetcher
from src.pipeline import run_layered_pipeline, run_pipeline


def register(cli: click.Group) -> None:
    """Attach the ``generate`` command to *cli*."""

    @cli.command()
    @dtm_option
    @dtm_dir_option
    @coordinate_options
    @mesh_options
    @click.option(
        "--hole-id",
        required=True,
        type=int,
        help="OpenStreetMap way ID of the golf hole (golf=hole way).",
    )
    @click.option(
        "--output",
        default="hole.stl",
        show_default=True,
        type=click.Path(),
        help=(
            "Output path.  For single-file mode: path to an .stl or .obj "
            "file.  For multi-tile directory mode (--dtm-dir): path to a "
            "directory or .zip file that will contain the three layer STLs."
        ),
    )
    def generate(
        dtm,
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
        """Generate a 3D model for a single par-3 hole specified by its OSM way ID.

        Accepts either a single DTM file (--dtm) for backward-compatible
        single-STL output, or a directory of tile files (--dtm-dir) with a
        centre coordinate (--lat / --lon) for layered multi-material output.
        """
        # ----------------------------------------------------------------
        # Validate mutually-exclusive / co-required inputs
        # ----------------------------------------------------------------
        if dtm is None and dtm_dir is None:
            raise click.UsageError(
                "Provide either --dtm (single file) or --dtm-dir (tile directory)."
            )
        if dtm is not None and dtm_dir is not None:
            raise click.UsageError(
                "--dtm and --dtm-dir are mutually exclusive."
            )
        if dtm_dir is not None and (lat is None or lon is None):
            raise click.UsageError(
                "--dtm-dir requires both --lat and --lon to define the study area."
            )

        # ----------------------------------------------------------------
        # Fetch hole geometry from OSM
        # ----------------------------------------------------------------
        click.echo(f"Fetching hole geometry for OSM way {hole_id} …")
        fetcher = CourseFetcher()
        geometry = fetcher.fetch_hole_by_id(hole_id)

        if geometry is None:
            click.echo(f"ERROR: Could not find OSM way {hole_id}.", err=True)
            sys.exit(1)

        # ----------------------------------------------------------------
        # Run the appropriate pipeline
        # ----------------------------------------------------------------
        if dtm_dir is not None:
            # Multi-tile directory mode: build VRT, crop to coordinate area,
            # generate three layer STLs.
            run_layered_pipeline(
                dtm_dir=dtm_dir,
                geometry=geometry,
                lat=lat,
                lon=lon,
                buffer_m=buffer,
                base_thickness=base_thickness,
                z_scale=z_scale,
                target_size_mm=target_size,
                output_path=output,
                label=f"OSM way {hole_id}",
            )
        else:
            # Single-file backward-compatible mode.
            run_pipeline(
                dtm_path=dtm,
                geometry=geometry,
                buffer_m=buffer,
                base_thickness=base_thickness,
                z_scale=z_scale,
                target_size_mm=target_size,
                output_path=output,
                label=f"OSM way {hole_id}",
            )
