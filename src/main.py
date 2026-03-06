"""
Golf Course 3D Generator – CLI entry point.

Usage examples
--------------
Generate a par-3 hole model by supplying an OSM way ID and a local DTM file::

    python -m src.main generate \\
        --dtm /data/terrain.tif \\
        --hole-id 123456789 \\
        --output /output/hole.stl

Search for par-3 holes near a lat/lon and generate all of them::

    python -m src.main generate-all \\
        --dtm /data/terrain.tif \\
        --lat 40.7128 --lon -74.0060 \\
        --radius 3000 \\
        --output-dir /output/

Run inside Docker (see docker-compose.yml for volume configuration)::

    docker compose run --rm generator generate \\
        --dtm /data/terrain.tif \\
        --hole-id 123456789 \\
        --output /output/hole.stl
"""

from __future__ import annotations

import sys

import click
import numpy as np
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from .course_fetcher import CourseFetcher
from .dtm_processor import DTMProcessor
from .exporter import ExportFormat, Exporter
from .mesh_generator import MeshGenerator


# ---------------------------------------------------------------------------
# Shared options factory
# ---------------------------------------------------------------------------

def _common_dtm_options(f):
    f = click.option(
        "--dtm",
        required=True,
        type=click.Path(exists=True, dir_okay=False),
        help="Path to a GeoTIFF DTM/DEM raster file.",
    )(f)
    return f


def _common_mesh_options(f):
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
            "Rescale the mesh so its longest horizontal dimension equals this "
            "value in millimetres.  When omitted the DTM's native units are used."
        ),
    )(f)
    return f


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option()
def cli():
    """Automate generation of 3D-printable par-3 golf hole models from DTM data."""


# ---------------------------------------------------------------------------
# 'generate' command – single hole by OSM way ID
# ---------------------------------------------------------------------------

@cli.command()
@_common_dtm_options
@_common_mesh_options
@click.option(
    "--hole-id",
    required=True,
    type=int,
    help="OpenStreetMap way ID of the golf hole (golf=hole way).",
)
@click.option(
    "--output",
    default="hole.stl",
    show_default=True,
    type=click.Path(),
    help="Output file path (.stl or .obj).",
)
def generate(dtm, hole_id, buffer, base_thickness, z_scale, target_size, output):
    """Generate a 3D model for a single par-3 hole specified by its OSM way ID."""
    click.echo(f"Fetching hole geometry for OSM way {hole_id} …")
    fetcher = CourseFetcher()
    geometry = fetcher.fetch_hole_by_id(hole_id)

    if geometry is None:
        click.echo(f"ERROR: Could not find OSM way {hole_id}.", err=True)
        sys.exit(1)

    _process_and_export(
        dtm_path=dtm,
        geometry=geometry,
        buffer_m=buffer,
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size,
        output_path=output,
        label=f"OSM way {hole_id}",
    )


# ---------------------------------------------------------------------------
# 'generate-all' command – all par-3 holes near a location
# ---------------------------------------------------------------------------

@cli.command(name="generate-all")
@_common_dtm_options
@_common_mesh_options
@click.option("--lat", required=True, type=float, help="Latitude of the search centre.")
@click.option("--lon", required=True, type=float, help="Longitude of the search centre.")
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
    help="Directory in which to write the generated STL files.",
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

        click.echo(f"  Processing {label} (OSM {osm_id})" + (f" – {name}" if name else ""))
        try:
            _process_and_export(
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
            click.echo(f"    WARNING: Failed to generate {label}: {exc}", err=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _buffer_wgs84_geometry(geometry: BaseGeometry, buffer_m: float) -> BaseGeometry:
    """Return *geometry* buffered by *buffer_m* metres using a UTM projection.

    The geometry is temporarily reprojected to a locally appropriate UTM zone
    (derived from its centroid), buffered there in metres, then projected back
    to WGS-84 (EPSG:4326).  This avoids the latitude-dependent inaccuracy of a
    simple degree-based buffer.
    """
    centroid = geometry.centroid
    lon, lat = centroid.x, centroid.y
    # Select the appropriate UTM zone
    utm_zone = int((lon + 180) / 6) + 1
    hemisphere = "north" if lat >= 0 else "south"
    utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

    to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

    geom_utm = shapely_transform(to_utm.transform, geometry)
    buffered_utm = geom_utm.buffer(buffer_m)
    return shapely_transform(to_wgs84.transform, buffered_utm)


def _process_and_export(
    dtm_path: str,
    geometry,
    buffer_m: float,
    base_thickness: float,
    z_scale: float,
    target_size_mm: float | None,
    output_path: str,
    label: str,
) -> None:
    """End-to-end pipeline: clip DTM → build mesh → export."""
    click.echo(f"  Clipping DTM to {label} boundary (buffer={buffer_m} m) …")

    # Buffer in degrees using a CRS-aware helper that reprojects to UTM,
    # applies the metric buffer, then reprojects back to WGS-84.
    buffered = _buffer_wgs84_geometry(geometry, buffer_m)

    with DTMProcessor(dtm_path) as proc:
        elevation, transform = proc.clip_to_geometry(buffered)

    elev_min = float(np.nanmin(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    elev_max = float(np.nanmax(elevation)) if not np.all(np.isnan(elevation)) else 0.0
    click.echo(
        f"  Elevation grid: {elevation.shape[0]}×{elevation.shape[1]}, "
        f"range [{elev_min:.1f} – {elev_max:.1f}]"
    )

    generator = MeshGenerator(
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
    )
    mesh = generator.generate(elevation, transform)

    fmt = ExportFormat.from_path(output_path)
    Exporter().export(mesh, output_path, fmt=fmt)
    click.echo(f"  ✓ Saved → {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
