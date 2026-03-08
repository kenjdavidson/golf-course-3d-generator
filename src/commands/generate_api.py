"""
``generate-api`` command – produce a 3D model for a single par-3 hole by
fetching elevation data from the Ontario ArcGIS ImageServer.

No local DTM files are required.  A 32-bit float GeoTIFF is downloaded
on-demand from the Ontario DTM LiDAR-Derived ImageServer for the bounding
box centred on ``--lat`` / ``--lon``.  Feature segmentation (greens/tees
and bunkers) is performed automatically using a Laplacian of Gaussian (LoG)
filter when no OSM hole outline is provided.

Usage
-----
Cloud-only (no OSM outline; LoG detects features)::

    python -m src.main generate-api \\
        --lat 43.5123 --lon -79.8765 \\
        --buffer 150 \\
        --output /output/hole3_layers

With optional OSM hole outline (clips the elevation raster to the exact
hole boundary; still no local files needed)::

    python -m src.main generate-api \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers

Inside Docker::

    docker compose run --rm generator generate-api \\
        --lat 43.5123 --lon -79.8765 \\
        --buffer 150 \\
        --output /output/hole3_layers

The output is a directory (or ``.zip`` if the path ends in ``.zip``)
containing three STL files for multi-material / filament-swap printing:

* ``base_terrain.stl`` – full terrain surface (structural body)
* ``green_inlay.stl``  – flat elevated plateaus (greens / tee colours)
* ``bunker_cutout.stl``– depression areas (sand / bunker filament)

For local DTM files, see the ``generate`` command.
"""

from __future__ import annotations

import sys

import click

from src.commands.options import coordinate_options, print_options
from src.course_fetcher import CourseFetcher
from src.generators.imageserver_generator import ImageServerHoleGenerator


def register(cli: click.Group) -> None:
    """Attach the ``generate-api`` command to *cli*."""

    @cli.command(name="generate-api")
    @coordinate_options
    @print_options
    @click.option(
        "--buffer",
        default=150,
        show_default=True,
        type=float,
        help=(
            "Half-width of the square bounding box (metres) fetched from the "
            "Ontario ArcGIS ImageServer.  A 150 m buffer yields a "
            "300 m × 300 m fetch area at 0.5 m/pixel (600 × 600 image)."
        ),
    )
    @click.option(
        "--hole-id",
        required=False,
        default=None,
        type=int,
        help=(
            "Optional OpenStreetMap way ID of the golf hole.  When supplied, "
            "the hole outline is used to clip the fetched elevation raster.  "
            "When omitted, features are detected automatically using the "
            "Laplacian of Gaussian (LoG) filter."
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
    def generate_api(
        lat,
        lon,
        buffer,
        hole_id,
        base_thickness,
        z_scale,
        target_size,
        output,
    ):
        """Generate a 3D model by fetching elevation from the Ontario ImageServer.

        No local files required.  Elevation is fetched as a 32-bit float
        GeoTIFF from the Ontario DTM LiDAR-Derived ImageServer.  Features
        (greens, bunkers) are detected via a Laplacian of Gaussian filter,
        or clipped from an OSM outline when ``--hole-id`` is supplied.

        Outputs three STL files (base_terrain, green_inlay, bunker_cutout)
        to a directory or ZIP archive for multi-material 3D printing.

        For local DTM files, use the ``generate`` command.
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

        generator = ImageServerHoleGenerator(
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
