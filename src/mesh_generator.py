"""
Mesh generator.

Converts a 2-D elevation array (from DTM) into a watertight 3-D mesh
suitable for 3D printing (solid base included).
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import rasterio.transform
import trimesh


class MeshGenerator:
    """Build a 3-D printable mesh from an elevation grid.

    Parameters
    ----------
    base_thickness:
        Thickness (in the same units as elevation data, typically metres)
        of the solid base added below the terrain surface.  A non-zero
        base ensures the model is watertight and printable.
    z_scale:
        Vertical exaggeration factor applied to elevation *relative to
        the minimum elevation*.  Use > 1 to emphasise relief.
    xy_scale:
        Horizontal scale factor applied to both x and y coordinates.
        Combine with *target_size_mm* for print-bed sizing.
    target_size_mm:
        If given, the mesh is rescaled so that its longest horizontal
        dimension equals this many millimetres.  Overrides *xy_scale*.
    """

    def __init__(
        self,
        base_thickness: float = 3.0,
        z_scale: float = 1.5,
        xy_scale: float = 1.0,
        target_size_mm: Optional[float] = None,
    ) -> None:
        self.base_thickness = base_thickness
        self.z_scale = z_scale
        self.xy_scale = xy_scale
        self.target_size_mm = target_size_mm

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(
        self,
        elevation: np.ndarray,
        transform: rasterio.transform.Affine,
    ) -> trimesh.Trimesh:
        """Build and return a watertight :class:`trimesh.Trimesh`.

        Parameters
        ----------
        elevation:
            2-D float array of elevation values (rows × cols).
            ``np.nan`` pixels are filled with the minimum valid elevation.
        transform:
            Rasterio affine transform mapping (col, row) → (x, y) in the
            DTM's CRS.

        Returns
        -------
        A :class:`trimesh.Trimesh` mesh ready for export.
        """
        elevation = self._fill_nan(elevation)

        rows, cols = elevation.shape
        xs, ys = self._build_coordinate_grids(rows, cols, transform)

        z_min = float(elevation.min())
        z_elevated = (elevation - z_min) * self.z_scale

        bottom_z = -self.base_thickness

        # ----------------------------------------------------------------
        # Build a single unified vertex array for a watertight solid:
        #   - [0 .. rows*cols)          : top surface vertices
        #   - [rows*cols .. rows*cols + P) : bottom-perimeter vertices (z = bottom_z)
        # ----------------------------------------------------------------
        # Top surface vertices
        top_verts = np.column_stack(
            [xs.ravel(), ys.ravel(), z_elevated.ravel()]
        )

        # Perimeter indices (CCW order: top-row → right-col → bottom-row-rev → left-col-rev)
        perim_indices = self._perimeter_indices(rows, cols)

        # Bottom perimeter vertices (same x,y, but at bottom_z)
        bottom_perim_verts = np.column_stack(
            [
                top_verts[perim_indices, 0],
                top_verts[perim_indices, 1],
                np.full(len(perim_indices), bottom_z),
            ]
        )

        all_vertices = np.vstack([top_verts, bottom_perim_verts])

        # Offset for bottom-perimeter vertices in the unified array
        bp_offset = len(top_verts)

        # ----------------------------------------------------------------
        # Faces
        # ----------------------------------------------------------------
        faces = []

        # 1. Top surface triangulation
        for r in range(rows - 1):
            for c in range(cols - 1):
                tl = r * cols + c
                tr = tl + 1
                bl = (r + 1) * cols + c
                br = bl + 1
                faces.append([tl, bl, tr])
                faces.append([tr, bl, br])

        # 2. Side walls: connect each perimeter edge to its bottom counterpart
        n_perim = len(perim_indices)
        for k in range(n_perim):
            next_k = (k + 1) % n_perim
            top_a = perim_indices[k]
            top_b = perim_indices[next_k]
            bot_a = bp_offset + k
            bot_b = bp_offset + next_k
            # Two triangles forming a quad panel
            faces.append([top_a, bot_a, top_b])
            faces.append([top_b, bot_a, bot_b])

        # 3. Bottom cap (fan triangulation from first bottom-perimeter vertex)
        bot_centre = bp_offset  # use first vertex as fan pivot
        for k in range(1, n_perim - 1):
            faces.append([bot_centre, bp_offset + k + 1, bp_offset + k])

        mesh = trimesh.Trimesh(
            vertices=all_vertices,
            faces=np.array(faces, dtype=np.int32),
            process=True,
        )

        # Rescale to target print size if requested
        if self.target_size_mm is not None:
            mesh = self._rescale_to_target(mesh, self.target_size_mm)
        elif self.xy_scale != 1.0:
            scale = np.array([self.xy_scale, self.xy_scale, 1.0])
            mesh.vertices *= scale

        return mesh

    # ------------------------------------------------------------------
    # Coordinate grid construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_coordinate_grids(
        rows: int, cols: int, transform: rasterio.transform.Affine
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return (xs, ys) grids of shape (rows, cols) in the DTM's CRS."""
        col_indices = np.arange(cols)
        row_indices = np.arange(rows)
        col_grid, row_grid = np.meshgrid(col_indices, row_indices)

        # rasterio transform: (col, row) -> (x, y) at pixel *centres*
        # Note: rasterio.transform.xy flattens the output, so we reshape.
        xs, ys = rasterio.transform.xy(transform, row_grid.ravel(), col_grid.ravel())
        xs = np.asarray(xs).reshape(rows, cols)
        ys = np.asarray(ys).reshape(rows, cols)
        return xs, ys

    # ------------------------------------------------------------------
    # Perimeter helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _perimeter_indices(rows: int, cols: int) -> list:
        """Return flattened vertex indices around the grid perimeter in CCW order.

        Order: top-row (left→right), right-col (top→bottom, skip top corner),
        bottom-row (right→left, skip right corner), left-col (bottom→top,
        skip bottom & top corners).
        """
        top = [c for c in range(cols)]                                  # (0,0) .. (0,cols-1)
        right = [r * cols + (cols - 1) for r in range(1, rows)]        # (1,cols-1) .. (rows-1,cols-1)
        bottom = [(rows - 1) * cols + c for c in range(cols - 2, -1, -1)]  # right→left
        left = [r * cols for r in range(rows - 2, 0, -1)]              # bottom-1 → 1
        return top + right + bottom + left

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fill_nan(elevation: np.ndarray) -> np.ndarray:
        """Replace NaN values with the minimum valid elevation."""
        arr = elevation.copy()
        if np.any(np.isnan(arr)):
            min_val = float(np.nanmin(arr)) if not np.all(np.isnan(arr)) else 0.0
            arr = np.where(np.isnan(arr), min_val, arr)
        return arr

    @staticmethod
    def _rescale_to_target(mesh: trimesh.Trimesh, target_mm: float) -> trimesh.Trimesh:
        """Scale mesh so that the longest XY dimension equals *target_mm*."""
        extents = mesh.bounding_box.extents  # (dx, dy, dz)
        max_xy = max(extents[0], extents[1])
        if max_xy > 0:
            scale_factor = target_mm / max_xy
            # Scale x and y only; z is already in meaningful units
            mesh.vertices[:, :2] *= scale_factor
        return mesh
