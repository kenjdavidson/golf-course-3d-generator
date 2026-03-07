"""
Shared Click option decorators used by more than one command.

Import the relevant decorators and stack them on any command function that
needs them::

    from src.commands.options import dtm_option, dtm_dir_option, mesh_options, coordinate_options

    @cli.command()
    @dtm_option
    @mesh_options
    def my_command(dtm, buffer, base_thickness, z_scale, target_size):
        ...

    # — or, for the multi-tile directory workflow —

    @cli.command()
    @dtm_dir_option
    @coordinate_options
    @mesh_options
    def my_command(dtm_dir, lat, lon, buffer, base_thickness, z_scale, target_size):
        ...
"""

from __future__ import annotations

import click


def dtm_option(f):
    """Add the ``--dtm`` option (path to a single GeoTIFF / VRT DTM file)."""
    return click.option(
        "--dtm",
        required=False,
        type=click.Path(exists=True, dir_okay=False),
        help=(
            "Path to a GeoTIFF or VRT DTM/DEM raster file.  Inside the "
            "Docker container this is typically /data/<filename>.tif.  "
            "Mutually exclusive with --dtm-dir."
        ),
    )(f)


def dtm_dir_option(f):
    """Add the ``--dtm-dir`` option (path to a directory of DTM tile files).

    When provided, the directory is automatically indexed into an
    ``index.vrt`` Virtual Raster (built with ``gdalbuildvrt``) if one does
    not already exist.  Must be used together with ``--lat`` / ``--lon`` to
    select the study area.
    """
    return click.option(
        "--dtm-dir",
        required=False,
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
        help=(
            "Path to a directory containing DTM/DEM tile files (.img).  "
            "An index.vrt is created automatically if absent.  "
            "Must be combined with --lat and --lon.  "
            "Mutually exclusive with --dtm."
        ),
    )(f)


def coordinate_options(f):
    """Add ``--lat`` and ``--lon`` options for coordinate-based area selection.

    These are used with ``--dtm-dir`` to define a 200 m × 200 m study area
    centred on the given WGS-84 coordinate.
    """
    f = click.option(
        "--lat",
        required=False,
        type=float,
        help=(
            "Latitude (WGS-84 decimal degrees) of the study-area centre.  "
            "Required when --dtm-dir is used."
        ),
    )(f)
    f = click.option(
        "--lon",
        required=False,
        type=float,
        help=(
            "Longitude (WGS-84 decimal degrees) of the study-area centre.  "
            "Required when --dtm-dir is used."
        ),
    )(f)
    return f


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
