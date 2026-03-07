"""
``generate`` command – produce a 3D model for a single par-3 hole.

The hole is identified by its OpenStreetMap way ID.  Find the ID by:

1. Visiting https://www.openstreetmap.org/ and navigating to the course.
2. Clicking the *Query features* tool and clicking on the hole outline.
3. Noting the **Way ID** shown in the panel (e.g. ``123456789``).

Example
-------
::

    python -m src.main generate \\
        --dtm /data/terrain.tif \\
        --hole-id 123456789 \\
        --output /output/hole3.stl \\
        --z-scale 1.5 \\
        --target-size 200

Inside Docker::

    docker compose run --rm generator generate \\
        --dtm /data/terrain.tif \\
        --hole-id 123456789 \\
        --output /output/hole3.stl
"""

from __future__ import annotations

import sys

import click

from src.commands.options import dtm_option, mesh_options
from src.course_fetcher import CourseFetcher
from src.pipeline import run_pipeline


def register(cli: click.Group) -> None:
    """Attach the ``generate`` command to *cli*."""

    @cli.command()
    @dtm_option
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
        help="Output file path (.stl or .obj).",
    )
    def generate(dtm, hole_id, buffer, base_thickness, z_scale, target_size, output):
        """Generate a 3D model for a single par-3 hole specified by its OSM way ID."""
        click.echo(f"Fetching hole geometry for OSM way {hole_id} …")
        fetcher = CourseFetcher()
        geometry = fetcher.fetch_hole_by_id(hole_id)

        if geometry is None:
            click.echo(f"ERROR: Could not find OSM way {hole_id}.", err=True)
            sys.exit(1)

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
