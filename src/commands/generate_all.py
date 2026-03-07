"""
``generate-all`` command – produce 3D models for every par-3 hole near a
given coordinate.

OpenStreetMap is queried for all ways tagged ``golf=hole`` + ``par=3``
within the specified search radius.  A separate STL/OBJ file is produced
for each hole found.

Example
-------
::

    python -m src.main generate-all \\
        --dtm /data/terrain.tif \\
        --lat 40.7128 --lon -74.0060 \\
        --radius 3000 \\
        --output-dir /output \\
        --z-scale 1.5

Inside Docker::

    docker compose run --rm generator generate-all \\
        --dtm /data/terrain.tif \\
        --lat 40.7128 --lon -74.0060 \\
        --radius 5000 \\
        --output-dir /output
"""

from __future__ import annotations

import sys

import click

from src.commands.options import dtm_option, mesh_options
from src.course_fetcher import CourseFetcher
from src.pipeline import run_pipeline


def register(cli: click.Group) -> None:
    """Attach the ``generate-all`` command to *cli*."""

    @cli.command(name="generate-all")
    @dtm_option
    @mesh_options
    @click.option(
        "--lat",
        required=True,
        type=float,
        help="Latitude of the search centre (WGS-84 decimal degrees).",
    )
    @click.option(
        "--lon",
        required=True,
        type=float,
        help="Longitude of the search centre (WGS-84 decimal degrees).",
    )
    @click.option(
        "--radius",
        default=5000,
        show_default=True,
        type=float,
        help="Search radius in metres.",
    )
    @click.option(
        "--output-dir",
        default="output",
        show_default=True,
        type=click.Path(),
        help="Directory in which to write the generated STL/OBJ files.",
    )
    @click.option(
        "--format",
        "fmt",
        default="stl",
        show_default=True,
        type=click.Choice(["stl", "obj"], case_sensitive=False),
        help="Output file format.",
    )
    def generate_all(
        dtm,
        lat,
        lon,
        radius,
        buffer,
        base_thickness,
        z_scale,
        target_size,
        output_dir,
        fmt,
    ):
        """Find all par-3 holes near LAT/LON and generate a 3D model for each."""
        click.echo(f"Searching for par-3 holes within {radius} m of ({lat}, {lon}) …")
        fetcher = CourseFetcher()
        holes = fetcher.fetch_par3_holes_near(lat, lon, radius_m=radius)

        if not holes:
            click.echo("No par-3 holes found in the search area.")
            sys.exit(0)

        click.echo(f"Found {len(holes)} par-3 hole(s).")

        for hole in holes:
            osm_id = hole["osm_id"]
            ref = hole.get("ref", "")
            name = hole.get("name", "")
            label = f"hole-{ref}" if ref else f"osm-{osm_id}"
            output_path = f"{output_dir}/{label}.{fmt.lower()}"

            click.echo(
                f"  Processing {label} (OSM {osm_id})"
                + (f" – {name}" if name else "")
            )
            try:
                run_pipeline(
                    dtm_path=dtm,
                    geometry=hole["geometry"],
                    buffer_m=buffer,
                    base_thickness=base_thickness,
                    z_scale=z_scale,
                    target_size_mm=target_size,
                    output_path=output_path,
                    label=label,
                )
            except Exception as exc:  # noqa: BLE001
                click.echo(
                    f"    WARNING: Failed to generate {label}: {exc}", err=True
                )
