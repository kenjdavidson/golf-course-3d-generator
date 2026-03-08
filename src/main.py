"""
Golf Course 3D Generator – CLI entry point.

This module defines the top-level Click group and registers all sub-commands.
See the individual command modules for usage details:

* :mod:`src.commands.generate`     – single hole from local DTM tile directory
* :mod:`src.commands.generate_all` – all par-3 holes near a coordinate, from local DTM
* :mod:`src.commands.generate_api` – single hole from Ontario ArcGIS ImageServer (no local files)

Quick start::

    # Single hole from local DTM files
    python -m src.main generate \\
        --dtm-dir /data/milton \\
        --hole-id 123456789 \\
        --lat 43.5123 --lon -79.8765 \\
        --output /output/hole3_layers

    # All par-3 holes near a location, from local DTM files
    python -m src.main generate-all \\
        --dtm-dir /data/milton \\
        --lat 43.5123 --lon -79.8765 \\
        --radius 3000 \\
        --output-dir /output/

    # Single hole via Ontario ArcGIS ImageServer (no local files)
    python -m src.main generate-api \\
        --lat 43.5123 --lon -79.8765 \\
        --buffer 150 \\
        --output /output/hole3_layers
"""

from __future__ import annotations

import click

from src.commands import generate as generate_cmd
from src.commands import generate_all as generate_all_cmd
from src.commands import generate_api as generate_api_cmd


@click.group()
@click.version_option()
def cli():
    """Automate generation of 3D-printable par-3 golf hole models from DTM data."""


generate_cmd.register(cli)
generate_all_cmd.register(cli)
generate_api_cmd.register(cli)


if __name__ == "__main__":
    cli()
