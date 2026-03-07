"""
Shared Click option decorators used by more than one command.

Import :func:`dtm_option` and :func:`mesh_options` and stack them on any
command function that needs them::

    from src.commands.options import dtm_option, mesh_options

    @cli.command()
    @dtm_option
    @mesh_options
    def my_command(dtm, buffer, base_thickness, z_scale, target_size):
        ...
"""

from __future__ import annotations

import click


def dtm_option(f):
    """Add the ``--dtm`` option (path to a GeoTIFF DTM file)."""
    return click.option(
        "--dtm",
        required=True,
        type=click.Path(exists=True, dir_okay=False),
        help=(
            "Path to a GeoTIFF DTM/DEM raster file.  Inside the Docker "
            "container this is typically /data/<filename>.tif."
        ),
    )(f)


def mesh_options(f):
    """Add the four mesh-quality options shared by all generate commands."""
    f = click.option(
        "--buffer",
        default=50,
        show_default=True,
        type=float,
        help="Buffer (metres) to add around the hole boundary before clipping.",
    )(f)
    f = click.option(
        "--base-thickness",
        default=3.0,
        show_default=True,
        type=float,
        help="Solid base thickness in metres (for 3D printing).",
    )(f)
    f = click.option(
        "--z-scale",
        default=1.5,
        show_default=True,
        type=float,
        help="Vertical exaggeration factor applied to terrain relief.",
    )(f)
    f = click.option(
        "--target-size",
        default=None,
        type=float,
        help=(
            "Rescale the mesh so its longest horizontal dimension equals "
            "this value in millimetres.  When omitted the DTM's native "
            "units are used."
        ),
    )(f)
    return f
