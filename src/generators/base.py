"""Abstract base class for all hole-model generators.

Every generator implements two abstract methods:

* :meth:`acquire_elevation` – obtain a NumPy elevation array and its
  rasterio affine transform from whatever data source the generator uses.
* :meth:`build_meshes` – convert the elevation array into a dictionary of
  named :class:`trimesh.Trimesh` objects (one per print layer).

The public entry point is :meth:`generate`, which orchestrates the full
pipeline and exports the resulting meshes to disk.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np
import click
import rasterio.transform

from ..exporter import Exporter
from ..mesh_generator import MeshGenerator


class HoleGenerator(ABC):
    """Abstract base for hole 3D model generators.

    Sub-classes provide the elevation acquisition strategy (local VRT or
    cloud service) and the feature-segmentation strategy.  The export logic
    is shared via the concrete :meth:`generate` method on this class.

    Parameters
    ----------
    base_thickness:
        Solid base depth in metres (3D printing).
    z_scale:
        Vertical exaggeration factor applied to terrain relief.
    target_size_mm:
        If given, the longest XY dimension of every mesh is rescaled to
        this value in millimetres.
    """

    def __init__(
        self,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        target_size_mm: Optional[float] = None,
    ) -> None:
        self.base_thickness = base_thickness
        self.z_scale = z_scale
        self.target_size_mm = target_size_mm

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(
        self,
        lat: float,
        lon: float,
        buffer_m: float,
        output_path: str,
        label: str = "",
        geometry=None,
    ) -> None:
        """Run the full acquisition → mesh → export pipeline.

        Parameters
        ----------
        lat:
            Latitude (WGS-84) of the study-area centre.
        lon:
            Longitude (WGS-84) of the study-area centre.
        buffer_m:
            Metric buffer added around the hole geometry before clipping
            (VRT path) or half-width of the bounding box requested from
            the ImageServer (cloud path).
        output_path:
            Destination directory path or ``.zip`` file path.
        label:
            Human-readable label for progress messages.
        geometry:
            Optional Shapely polygon for the golf hole in WGS-84
            coordinates.  When ``None``, the generator falls back to its
            own area derivation (e.g. coordinate + buffer).
        """
        elevation, transform = self.acquire_elevation(
            lat, lon, buffer_m, geometry, label
        )
        self._log_grid(elevation)
        meshes = self.build_meshes(elevation, transform)
        self._export(meshes, output_path)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def acquire_elevation(
        self,
        lat: float,
        lon: float,
        buffer_m: float,
        geometry,
        label: str,
    ) -> Tuple[np.ndarray, rasterio.transform.Affine]:
        """Acquire elevation data and return ``(elevation_array, affine_transform)``.

        Parameters
        ----------
        lat:
            Latitude of the study-area centre (WGS-84 decimal degrees).
        lon:
            Longitude of the study-area centre (WGS-84 decimal degrees).
        buffer_m:
            Fetch radius / buffer in metres.
        geometry:
            Optional Shapely geometry for clipping.
        label:
            Human-readable label for log messages.
        """

    @abstractmethod
    def build_meshes(
        self,
        elevation: np.ndarray,
        transform: rasterio.transform.Affine,
    ) -> dict:
        """Build layer meshes from *elevation* and return a ``name → Trimesh`` dict."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _make_mesh_generator(self) -> MeshGenerator:
        """Return a :class:`~src.mesh_generator.MeshGenerator` configured from this generator's settings."""
        return MeshGenerator(
            base_thickness=self.base_thickness,
            z_scale=self.z_scale,
            target_size_mm=self.target_size_mm,
        )

    def _log_grid(self, elevation: np.ndarray) -> None:
        """Emit a Click echo with elevation grid statistics."""
        elev_min = float(np.nanmin(elevation)) if not np.all(np.isnan(elevation)) else 0.0
        elev_max = float(np.nanmax(elevation)) if not np.all(np.isnan(elevation)) else 0.0
        click.echo(
            f"  Elevation grid: {elevation.shape[0]}×{elevation.shape[1]}, "
            f"range [{elev_min:.1f} – {elev_max:.1f}]"
        )

    def _export(self, meshes: dict, output_path: str) -> None:
        """Write *meshes* to *output_path* (directory or ``.zip``)."""
        exporter = Exporter()
        if output_path.endswith(".zip"):
            exporter.export_layers_to_zip(meshes, output_path)
            click.echo(f"  ✓ Layers saved → {output_path}")
        else:
            exporter.export_layers_to_dir(meshes, output_path)
            for name in meshes:
                click.echo(
                    f"  ✓ {name}.stl → {os.path.join(output_path, name + '.stl')}"
                )
