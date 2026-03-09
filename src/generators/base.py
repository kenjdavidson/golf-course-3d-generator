"""Abstract base class for all hole-model generators.

Every generator implements one abstract method:

* :meth:`acquire_elevation` – obtain a NumPy elevation array and its
  rasterio affine transform from whatever data source the generator uses.

The conversion of the elevation array into meshes is delegated to a
:class:`~src.processors.base.MeshProcessor`, and the export of those meshes
is delegated to an :class:`~src.outputs.base.OutputWriter`.  Both can be
injected at construction time to customise the pipeline without modifying the
generator sub-classes.

The public entry point is :meth:`generate`, which orchestrates the full
pipeline: acquire → process → write.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np
import click
import rasterio.transform

from ..mesh_generator import MeshGenerator
from ..outputs.base import OutputWriter
from ..outputs.layered_stl_output import LayeredSTLOutput
from ..processors.base import MeshProcessor


class HoleGenerator(ABC):
    """Abstract base for hole 3D model generators.

    Sub-classes provide the elevation acquisition strategy (local VRT or
    cloud service) and set a default :class:`~src.processors.base.MeshProcessor`.
    The mesh-construction and file-export stages are fully decoupled via the
    ``processor`` and ``output_writer`` injection points.

    Parameters
    ----------
    base_thickness:
        Solid base depth in metres (3D printing).  Forwarded to the default
        processor when no explicit *processor* is supplied.
    z_scale:
        Vertical exaggeration factor applied to terrain relief.  Forwarded to
        the default processor when no explicit *processor* is supplied.
    target_size_mm:
        If given, the longest XY dimension of every mesh is rescaled to this
        value in millimetres.  Forwarded to the default processor when no
        explicit *processor* is supplied.
    processor:
        :class:`~src.processors.base.MeshProcessor` instance used to convert
        the elevation array into layer meshes.  When ``None``, each concrete
        sub-class supplies a suitable default processor in its constructor.
    output_writer:
        :class:`~src.outputs.base.OutputWriter` instance used to persist the
        generated meshes.  Defaults to
        :class:`~src.outputs.layered_stl_output.LayeredSTLOutput` (three STL
        files, or a ZIP archive when the path ends in ``.zip``).
    """

    def __init__(
        self,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        target_size_mm: Optional[float] = None,
        processor: Optional[MeshProcessor] = None,
        output_writer: Optional[OutputWriter] = None,
    ) -> None:
        self.base_thickness = base_thickness
        self.z_scale = z_scale
        self.target_size_mm = target_size_mm
        # processor may be None here; concrete sub-classes set a default in __init__
        self.processor = processor
        self.output_writer = output_writer or LayeredSTLOutput()

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
        """Run the full acquisition → process → write pipeline.

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
        processor = self._get_processor()
        meshes = processor.build_meshes(elevation, transform)
        self.output_writer.write(meshes, output_path)

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

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _get_processor(self) -> MeshProcessor:
        """Return the active :class:`~src.processors.base.MeshProcessor`.

        If no processor was injected and the sub-class did not set one,
        falls back to a :class:`~src.processors.gradient_processor.GradientMeshProcessor`
        with this generator's mesh settings.
        """
        if self.processor is not None:
            return self.processor
        from ..processors.gradient_processor import GradientMeshProcessor
        return GradientMeshProcessor(
            base_thickness=self.base_thickness,
            z_scale=self.z_scale,
            target_size_mm=self.target_size_mm,
        )

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
