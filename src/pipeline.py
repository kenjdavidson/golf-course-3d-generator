"""
Core end-to-end pipeline used by every CLI command.

This module wires together the four processing stages:

1. :func:`buffer_wgs84_geometry` – expand a WGS-84 polygon outward by a
   metric distance using a UTM reprojection.
2. **DTM acquisition** – either:

   a. :class:`~src.vrt_builder.VRTBuilder` + :class:`~src.dtm_processor.DTMProcessor`
      when a local ``--dtm-dir`` is provided (multi-tile VRT path), or
   b. :class:`~src.services.ontario_geohub.OntarioGeohubClient` to fetch a
      32-bit float GeoTIFF from the Ontario ArcGIS ImageServer when no local
      data directory is given (cloud-native path).

3. :class:`~src.mesh_generator.MeshGenerator` – convert the elevation grid
   to a set of watertight 3-D meshes.  When the cloud-native path is used
   and no hole geometry is available, feature masks are derived from
   :class:`~src.services.feature_extractor.FeatureExtractor`.
4. :class:`~src.exporter.Exporter` – write the layer pack to disk.

The single top-level entry point is :func:`run_layered_pipeline`, which
builds a VRT index (or fetches from the cloud) automatically,
crops to a 200 m × 200 m study area, and outputs three STL files:
``base_terrain``, ``green_inlay``, and ``bunker_cutout``.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import click
from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from .dtm_processor import DTMProcessor
from .exporter import Exporter
from .mesh_generator import MeshGenerator
from .vrt_builder import VRTBuilder
from .services.feature_extractor import FeatureExtractor
from .services.ontario_geohub import OntarioGeohubClient

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
    """Multi-tile VRT or cloud-native pipeline that outputs three layer STL files.

    Workflow – local VRT path (``dtm_dir`` is provided)
    -----------------------------------------------------
    1. :class:`~src.vrt_builder.VRTBuilder` builds (or reuses) ``index.vrt``
       from the tile files in *dtm_dir*.
    2. A 200 m × 200 m study-area bounding box is derived from *lat* / *lon*
       and intersected with the hole geometry / buffer.
    3. The elevation grid is clipped from the VRT using
       :class:`~src.dtm_processor.DTMProcessor`.
    4. :meth:`~src.mesh_generator.MeshGenerator.generate_layers` produces
       three meshes: ``base_terrain``, ``green_inlay``, ``bunker_cutout``.

    Workflow – cloud-native path (``dtm_dir`` is ``None``)
    -------------------------------------------------------
    1. :class:`~src.services.ontario_geohub.OntarioGeohubClient` fetches a
       32-bit float GeoTIFF from the Ontario ArcGIS ImageServer.
    2. The elevation grid is loaded from the temporary GeoTIFF.  If a hole
       *geometry* is available it is used to clip the raster; otherwise the
       full fetched extent is used.
    3. :class:`~src.services.feature_extractor.FeatureExtractor` derives
       green and bunker masks from the raw elevation data using
       ``skimage.measure`` connected-component labelling.
    4. Three meshes are built from the masked elevation arrays.

    In both workflows the meshes are written to *output_path*:
    - If *output_path* ends in ``.zip`` → a single ZIP archive.
    - Otherwise → a directory containing three ``.stl`` files.

    Parameters
    ----------
    geometry:
        Shapely polygon for the golf hole in WGS-84 coordinates, or ``None``
        to use the raw fetched/clipped area without an OSM outline.
    lat:
        Latitude (WGS-84) of the study-area centre.
    lon:
        Longitude (WGS-84) of the study-area centre.
    buffer_m:
        Metric buffer added around the hole geometry before clipping (VRT
        path), or half-width of the bounding box fetched from the ImageServer
        (cloud-native path).
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
    dtm_dir:
        Directory containing DTM tile files (e.g. ``.img`` or ``.tif``).
        Pass ``None`` (default) to use the Ontario ArcGIS ImageServer.
    """
    if dtm_dir is not None:
        elevation, transform = _acquire_elevation_vrt(
            dtm_dir, geometry, lat, lon, buffer_m, label
        )
    else:
        elevation, transform = _acquire_elevation_cloud(
            lat, lon, buffer_m, geometry, label
        )

    elev_min = float(np.nanmin(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    elev_max = float(np.nanmax(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    click.echo(
        f"  Elevation grid: {elevation.shape[0]}×{elevation.shape[1]}, "
        f"range [{elev_min:.1f} – {elev_max:.1f}]"
    )

    # Build three layer meshes.
    gen = MeshGenerator(
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
    )

    if dtm_dir is not None:
        # VRT path: use existing gradient/threshold approach inside generate_layers.
        meshes = gen.generate_layers(elevation, transform)
    else:
        # Cloud-native path: use FeatureExtractor (skimage/scipy) for masks.
        meshes = _generate_layers_cloud(gen, elevation, transform)

    # Export to directory or ZIP.
    exporter = Exporter()
    if output_path.endswith(".zip"):
        exporter.export_layers_to_zip(meshes, output_path)
        click.echo(f"  ✓ Layers saved → {output_path}")
    else:
        exporter.export_layers_to_dir(meshes, output_path)
        for name in meshes:
            click.echo(f"  ✓ {name}.stl → {os.path.join(output_path, name + '.stl')}")


# ---------------------------------------------------------------------------
# Private acquisition helpers
# ---------------------------------------------------------------------------


def _acquire_elevation_vrt(
    dtm_dir: str,
    geometry: Optional[BaseGeometry],
    lat: float,
    lon: float,
    buffer_m: float,
    label: str,
):
    """Clip elevation from a local VRT index and return (elevation, transform).

    Builds (or reuses) ``index.vrt`` from *dtm_dir*, then clips to the
    intersection of the buffered *geometry* and the 200 m study area.
    """
    builder = VRTBuilder(dtm_dir)
    vrt_path = builder.ensure_vrt()
    click.echo(f"  VRT index: {vrt_path}")

    study_area = _coordinate_to_study_area(lat, lon)

    if geometry is not None:
        buffered_hole = buffer_wgs84_geometry(geometry, buffer_m)
        clip_geom = buffered_hole.intersection(study_area)
        if clip_geom.is_empty:
            clip_geom = study_area
    else:
        clip_geom = study_area

    click.echo(f"  Clipping VRT to {label} study area (±{_STUDY_AREA_RADIUS_M} m) …")

    with DTMProcessor(vrt_path) as proc:
        elevation, transform = proc.clip_to_geometry(clip_geom)

    return elevation, transform


def _acquire_elevation_cloud(
    lat: float,
    lon: float,
    buffer_m: float,
    geometry: Optional[BaseGeometry],
    label: str,
):
    """Fetch elevation from the Ontario ArcGIS ImageServer and return (elevation, transform).

    Downloads a 32-bit float GeoTIFF for the bounding box defined by
    *lat* / *lon* ± *buffer_m* metres.  If a hole *geometry* is provided
    the raster is further clipped to it; otherwise the full fetched extent
    is used.
    """
    click.echo(
        f"  Fetching elevation from Ontario ImageServer for {label} "
        f"(buffer={buffer_m} m) …"
    )
    client = OntarioGeohubClient()
    tmp_path = client.fetch_elevation_tiff(lat, lon, buffer_m)

    try:
        with DTMProcessor(tmp_path) as proc:
            if geometry is not None:
                elevation, transform = proc.clip_to_geometry(geometry)
            else:
                # No geometry – use the full fetched extent.
                b = proc.bounds
                elevation, transform = proc.clip_to_bounds(
                    (b.left, b.bottom, b.right, b.top)
                )
    finally:
        os.unlink(tmp_path)

    return elevation, transform


def _generate_layers_cloud(
    gen: MeshGenerator,
    elevation: np.ndarray,
    transform,
) -> dict:
    """Build three layer meshes using :class:`~src.services.feature_extractor.FeatureExtractor`.

    Uses scikit-image connected-component labelling and SciPy morphological
    operations to detect plateau (green) and depression (bunker) regions,
    then delegates mesh construction to *gen*.

    Parameters
    ----------
    gen:
        A configured :class:`~src.mesh_generator.MeshGenerator` instance.
    elevation:
        Raw elevation array (may contain NaN).
    transform:
        Rasterio affine transform for the grid.

    Returns
    -------
    dict
        Mapping ``"base_terrain"``, ``"green_inlay"``, ``"bunker_cutout"`` →
        :class:`trimesh.Trimesh`.
    """
    extractor = FeatureExtractor()
    green_mask = extractor.extract_green_mask(elevation)
    bunker_mask = extractor.extract_bunker_mask(elevation)

    filled = MeshGenerator._fill_nan(elevation)
    green_elev = np.where(green_mask, filled, np.nan)
    bunker_elev = np.where(bunker_mask, filled, np.nan)

    return {
        "base_terrain": gen.generate(elevation, transform),
        "green_inlay": gen.generate(green_elev, transform),
        "bunker_cutout": gen.generate(bunker_elev, transform),
    }
