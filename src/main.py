"""
Golf Course 3D Generator – CLI entry point.

This module defines the top-level Click group and registers all sub-commands.
See the individual command modules for usage details:

* :mod:`src.commands.generate`     – single hole by OSM way ID
* :mod:`src.commands.generate_all` – all par-3 holes near a coordinate

Quick start::

    # Single hole
    python -m src.main generate \\
        --dtm /data/terrain.tif \\
        --hole-id 123456789 \\
        --output /output/hole.stl

    # All par-3 holes near a location
    python -m src.main generate-all \\
        --dtm /data/terrain.tif \\
        --lat 40.7128 --lon -74.0060 \\
        --radius 3000 \\
        --output-dir /output/
"""

from __future__ import annotations

import click

from src.commands import generate as generate_cmd
from src.commands import generate_all as generate_all_cmd


@click.group()
@click.version_option()
def cli():
    """Automate generation of 3D-printable par-3 golf hole models from DTM data."""


generate_cmd.register(cli)
generate_all_cmd.register(cli)


if __name__ == "__main__":
    cli()
