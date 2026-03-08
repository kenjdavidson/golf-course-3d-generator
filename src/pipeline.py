"""Core end-to-end pipeline – compatibility shim.

The generation logic now lives in :mod:`src.generators`.  This module
re-exports the public utilities that were previously defined here and
provides a backward-compatible :func:`run_layered_pipeline` wrapper that
delegates to the appropriate :class:`~src.generators.base.HoleGenerator`.

Public surface
--------------
* :func:`buffer_wgs84_geometry` – buffer a WGS-84 geometry by metres.
* :func:`run_layered_pipeline` – full acquisition → mesh → export pipeline.
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry.base import BaseGeometry

# Re-export utilities from geo_utils for backward compatibility.
from .geo_utils import buffer_wgs84_geometry, coordinate_to_study_area  # noqa: F401
from .generators.factory import create_generator


def run_layered_pipeline(
    geometry: Optional[BaseGeometry],
    lat: float,
    lon: float,
    buffer_m: float,
    base_thickness: float,
    z_scale: float,
    target_size_mm: Optional[float],
    output_path: str,
    label: str,
    dtm_dir: Optional[str] = None,
) -> None:
    """Run the full acquisition → mesh → export pipeline.

    This is a thin wrapper around :func:`~src.generators.factory.create_generator`
    kept for backward compatibility with callers that imported from this module
    before the generator refactor.

    For new code prefer using :func:`~src.generators.factory.create_generator`
    directly::

        from src.generators.factory import create_generator

        gen = create_generator(dtm_dir="/data/milton")
        gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/out/hole")

    Parameters
    ----------
    geometry:
        Shapely polygon for the golf hole in WGS-84, or ``None``.
    lat, lon:
        WGS-84 study-area centre.
    buffer_m:
        Metric buffer / fetch half-width.
    base_thickness:
        Solid base depth in metres.
    z_scale:
        Vertical exaggeration factor.
    target_size_mm:
        Optional print-bed rescaling.
    output_path:
        Destination directory or ``.zip`` path.
    label:
        Human-readable label for progress messages.
    dtm_dir:
        Local DTM tile directory.  ``None`` → Ontario ImageServer.
    """
    generator = create_generator(
        dtm_dir=dtm_dir,
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
    )
    generator.generate(
        lat=lat,
        lon=lon,
        buffer_m=buffer_m,
        output_path=output_path,
        label=label,
        geometry=geometry,
    )
