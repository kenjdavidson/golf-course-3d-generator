"""
Core end-to-end pipeline used by every CLI command.

This module wires together the four processing stages:

1. :func:`buffer_wgs84_geometry` – expand a WGS-84 polygon outward by a
   metric distance using a UTM reprojection.
2. :class:`~src.dtm_processor.DTMProcessor` – clip the GeoTIFF (or VRT)
   raster to the buffered geometry.
3. :class:`~src.mesh_generator.MeshGenerator` – convert the elevation grid
   to a watertight 3-D mesh.
4. :class:`~src.exporter.Exporter` – write the mesh (or layer pack) to disk.

Two top-level entry points are provided:

* :func:`run_pipeline` – single-STL output (backward-compatible).
* :func:`run_layered_pipeline` – multi-tile VRT workflow that outputs three
  STL files (``base_terrain``, ``green_inlay``, ``bunker_cutout``) to a
  directory or ``.zip`` archive.
"""

from __future__ import annotations

import os

import numpy as np
import click
from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from .dtm_processor import DTMProcessor
from .exporter import ExportFormat, Exporter
from .mesh_generator import MeshGenerator
from .vrt_builder import VRTBuilder

# Half-width in metres of the study-area bounding box when --lat/--lon are
# used with --dtm-dir.  A 100 m radius gives a ≈200 m × 200 m square.
_STUDY_AREA_RADIUS_M = 100


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


def _coordinate_to_study_area(lat: float, lon: float) -> BaseGeometry:
    """Return a ~200 m × 200 m WGS-84 bounding box centred on *lat* / *lon*.

    The box is derived by buffering the coordinate point by
    :data:`_STUDY_AREA_RADIUS_M` metres in UTM space and taking the
    rectangular envelope of the resulting circle.

    Parameters
    ----------
    lat:
        Latitude in decimal degrees (WGS-84).
    lon:
        Longitude in decimal degrees (WGS-84).

    Returns
    -------
    Shapely geometry in WGS-84 that covers the study area.
    """
    centre = Point(lon, lat)
    buffered = buffer_wgs84_geometry(centre, _STUDY_AREA_RADIUS_M)
    # Use the rectangular envelope so the clip region is axis-aligned.
    return buffered.envelope


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
        Path to the GeoTIFF (or VRT) DTM file.
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


def run_layered_pipeline(
    dtm_dir: str,
    geometry: BaseGeometry,
    lat: float,
    lon: float,
    buffer_m: float,
    base_thickness: float,
    z_scale: float,
    target_size_mm: float | None,
    output_path: str,
    label: str,
) -> None:
    """Multi-tile VRT pipeline that outputs three layer STL files.

    Workflow
    --------
    1. :class:`~src.vrt_builder.VRTBuilder` builds (or reuses) ``index.vrt``
       from the ``.img`` files in *dtm_dir*.
    2. A 200 m × 200 m study-area bounding box is derived from *lat* / *lon*
       and intersected with the hole geometry / buffer.
    3. The elevation grid is clipped from the VRT using
       :class:`~src.dtm_processor.DTMProcessor`.
    4. :meth:`~src.mesh_generator.MeshGenerator.generate_layers` produces
       three meshes: ``base_terrain``, ``green_inlay``, ``bunker_cutout``.
    5. The meshes are written to *output_path*:
       - If *output_path* ends in ``.zip`` → a single ZIP archive.
       - Otherwise → a directory containing three ``.stl`` files.

    Parameters
    ----------
    dtm_dir:
        Directory containing ``.img`` tile files.
    geometry:
        Shapely polygon for the golf hole in WGS-84 coordinates.
    lat:
        Latitude (WGS-84) of the study-area centre.
    lon:
        Longitude (WGS-84) of the study-area centre.
    buffer_m:
        Metric buffer added around the hole geometry before clipping.
    base_thickness:
        Solid base depth in metres.
    z_scale:
        Vertical exaggeration factor.
    target_size_mm:
        Optional print-bed rescaling (longest XY → this many mm).
    output_path:
        Destination directory path or ``.zip`` file path.
    label:
        Human-readable label for progress messages.
    """
    # 1. Build / reuse VRT index.
    builder = VRTBuilder(dtm_dir)
    vrt_path = builder.ensure_vrt()
    click.echo(f"  VRT index: {vrt_path}")

    # 2. Determine clip geometry.
    #    Use the intersection of the hole buffer and the 200 m study area so
    #    that the clip region is always within the study-area extent.
    study_area = _coordinate_to_study_area(lat, lon)
    buffered_hole = buffer_wgs84_geometry(geometry, buffer_m)
    clip_geom = buffered_hole.intersection(study_area)
    if clip_geom.is_empty:
        # Fall back to just the study area if there is no overlap.
        clip_geom = study_area

    click.echo(f"  Clipping VRT to {label} study area (±{_STUDY_AREA_RADIUS_M} m) …")

    # 3. Clip elevation from VRT.
    with DTMProcessor(vrt_path) as proc:
        elevation, transform = proc.clip_to_geometry(clip_geom)

    elev_min = float(np.nanmin(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    elev_max = float(np.nanmax(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    click.echo(
        f"  Elevation grid: {elevation.shape[0]}×{elevation.shape[1]}, "
        f"range [{elev_min:.1f} – {elev_max:.1f}]"
    )

    # 4. Generate three layer meshes.
    meshes = MeshGenerator(
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
    ).generate_layers(elevation, transform)

    # 5. Export to directory or ZIP.
    exporter = Exporter()
    if output_path.endswith(".zip"):
        exporter.export_layers_to_zip(meshes, output_path)
        click.echo(f"  ✓ Layers saved → {output_path}")
    else:
        exporter.export_layers_to_dir(meshes, output_path)
        for name in meshes:
            click.echo(f"  ✓ {name}.stl → {os.path.join(output_path, name + '.stl')}")
