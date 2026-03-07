"""
Core end-to-end pipeline used by every CLI command.

This module wires together the four processing stages:

1. :func:`_buffer_wgs84_geometry` – expand a WGS-84 polygon outward by a
   metric distance using a UTM reprojection.
2. :class:`~src.dtm_processor.DTMProcessor` – clip the GeoTIFF raster to the
   buffered geometry.
3. :class:`~src.mesh_generator.MeshGenerator` – convert the elevation grid to
   a watertight 3-D mesh.
4. :class:`~src.exporter.Exporter` – write the mesh to disk as STL or OBJ.
"""

from __future__ import annotations

import numpy as np
import click
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from .dtm_processor import DTMProcessor
from .exporter import ExportFormat, Exporter
from .mesh_generator import MeshGenerator


def buffer_wgs84_geometry(geometry: BaseGeometry, buffer_m: float) -> BaseGeometry:
    """Return *geometry* buffered by *buffer_m* metres using a UTM projection.

    The geometry is temporarily reprojected to a locally appropriate UTM zone
    (derived from its centroid), buffered there in metres, then projected back
    to WGS-84 (EPSG:4326).  This avoids the latitude-dependent inaccuracy of a
    simple degree-based buffer.

    Parameters
    ----------
    geometry:
        Input Shapely geometry in WGS-84 (EPSG:4326).
    buffer_m:
        Buffer radius in metres.

    Returns
    -------
    Buffered geometry in WGS-84.
    """
    centroid = geometry.centroid
    lon, lat = centroid.x, centroid.y
    utm_zone = int((lon + 180) / 6) + 1
    hemisphere = "north" if lat >= 0 else "south"
    utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

    to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

    geom_utm = shapely_transform(to_utm.transform, geometry)
    buffered_utm = geom_utm.buffer(buffer_m)
    return shapely_transform(to_wgs84.transform, buffered_utm)


def run_pipeline(
    dtm_path: str,
    geometry: BaseGeometry,
    buffer_m: float,
    base_thickness: float,
    z_scale: float,
    target_size_mm: float | None,
    output_path: str,
    label: str,
) -> None:
    """Execute the full DTM-clip → mesh-build → export pipeline.

    Parameters
    ----------
    dtm_path:
        Path to the GeoTIFF DTM file (inside the container: ``/data/…``).
    geometry:
        Shapely polygon for the golf hole in WGS-84 coordinates.
    buffer_m:
        Metric buffer to add around *geometry* before clipping the DTM.
    base_thickness:
        Solid base depth (metres) added below the terrain surface.
    z_scale:
        Vertical exaggeration factor applied to terrain relief.
    target_size_mm:
        When set, the mesh is rescaled so its longest XY dimension equals
        this many millimetres.
    output_path:
        Destination file path for the generated STL/OBJ mesh.
    label:
        Human-readable label used in progress messages.
    """
    click.echo(f"  Clipping DTM to {label} boundary (buffer={buffer_m} m) …")

    buffered = buffer_wgs84_geometry(geometry, buffer_m)

    with DTMProcessor(dtm_path) as proc:
        elevation, transform = proc.clip_to_geometry(buffered)

    elev_min = float(np.nanmin(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    elev_max = float(np.nanmax(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    click.echo(
        f"  Elevation grid: {elevation.shape[0]}×{elevation.shape[1]}, "
        f"range [{elev_min:.1f} – {elev_max:.1f}]"
    )

    mesh = MeshGenerator(
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
    ).generate(elevation, transform)

    fmt = ExportFormat.from_path(output_path)
    Exporter().export(mesh, output_path, fmt=fmt)
    click.echo(f"  ✓ Saved → {output_path}")
