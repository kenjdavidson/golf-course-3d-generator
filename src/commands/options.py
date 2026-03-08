"""
Shared Click option decorators used by more than one command.

Import the relevant decorators and stack them on any command function that
needs them::

    from src.commands.options import dtm_dir_option, coordinate_options, print_options

    @cli.command()
    @dtm_dir_option
    @coordinate_options
    @print_options
    def my_command(dtm_dir, lat, lon, base_thickness, z_scale, target_size):
        ...
"""

from __future__ import annotations

import click


def dtm_dir_option(f):
    """Add the ``--dtm-dir`` option (required path to a directory of DTM tile files).

    The directory is automatically indexed into an ``index.vrt`` Virtual
    Raster (built with ``gdalbuildvrt``) if one does not already exist.
    This option is required for commands that process local DTM data.
    """
    return click.option(
        "--dtm-dir",
        required=True,
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
        help=(
            "Path to a directory containing DTM/DEM tile files (.img or .tif).  "
            "An index.vrt is created automatically if absent."
        ),
    )(f)


def coordinate_options(f):
    """Add ``--lat`` and ``--lon`` options for coordinate-based area selection.

    These define a 200 m × 200 m study area centred on the given WGS-84
    coordinate.
    """
    f = click.option(
        "--lat",
        required=True,
        type=float,
        help="Latitude (WGS-84 decimal degrees) of the study-area centre.",
    )(f)
    f = click.option(
        "--lon",
        required=True,
        type=float,
        help="Longitude (WGS-84 decimal degrees) of the study-area centre.",
    )(f)
    return f


def print_options(f):
    """Add the three mesh-quality / print-quality options shared by all generate commands.

    Covers vertical scale, base thickness, and optional print-bed rescaling.
    Each command adds its own ``--buffer`` with a purpose-appropriate default.
    """
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


# ---------------------------------------------------------------------------
# Backward-compat alias: mesh_options = print_options + --buffer
# ---------------------------------------------------------------------------

def mesh_options(f):
    """Add mesh-quality options including ``--buffer`` (50 m default).

    .. deprecated::
        Prefer ``print_options`` plus an explicit ``--buffer`` option in each
        command so the default can be tuned to the command's purpose.
    """
    f = click.option(
        "--buffer",
        default=50,
        show_default=True,
        type=float,
        help="Buffer (metres) to add around the hole boundary before clipping.",
    )(f)
    return print_options(f)
