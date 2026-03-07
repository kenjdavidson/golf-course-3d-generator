"""VRT (Virtual Raster) builder.

Handles automatic indexing of multi-tile DTM datasets (e.g. the Ontario
DTM Milton Package, which ships as 249 individual ``.img`` files) into a
single GDAL Virtual Raster (``.vrt``) file.  The resulting VRT is a
lightweight XML descriptor — no data is copied — and is fully understood
by :class:`~src.dtm_processor.DTMProcessor` (via rasterio).

Overview
--------
::

    builder = VRTBuilder("/data/milton")
    vrt_path = builder.ensure_vrt()   # builds /data/milton/index.vrt if absent
    # vrt_path → "/data/milton/index.vrt"

    with DTMProcessor(vrt_path) as proc:
        elevation, transform = proc.clip_to_bounds(...)

The VRT is created by calling ``gdalbuildvrt`` (from the ``gdal-bin``
package).  An existing ``index.vrt`` is reused without rebuilding.

Example usage
-------------
::

    from src.vrt_builder import VRTBuilder

    builder = VRTBuilder("/data/ontario_milton", tile_pattern="*.img")
    vrt_path = builder.ensure_vrt()
    print(vrt_path)  # /data/ontario_milton/index.vrt
"""

from __future__ import annotations

import glob
import os
import subprocess


class VRTBuilder:
    """Build or reuse a GDAL Virtual Raster index for a directory of tiles.

    Parameters
    ----------
    data_dir:
        Directory containing raster tile files (e.g. ``.img``).
    vrt_filename:
        Name of the VRT file to create inside *data_dir*.  Defaults to
        ``"index.vrt"``.
    tile_pattern:
        Glob pattern for raster tiles within *data_dir*.  Defaults to
        ``"*.img"``.

    Raises
    ------
    FileNotFoundError
        If *data_dir* does not exist.
    """

    def __init__(
        self,
        data_dir: str,
        vrt_filename: str = "index.vrt",
        tile_pattern: str = "*.img",
    ) -> None:
        self.data_dir = os.path.abspath(data_dir)
        self.vrt_path = os.path.join(self.data_dir, vrt_filename)
        self.tile_pattern = tile_pattern

        if not os.path.isdir(self.data_dir):
            raise FileNotFoundError(
                f"Data directory does not exist: {self.data_dir!r}"
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ensure_vrt(self) -> str:
        """Return the path to a VRT, building it first if it does not exist.

        If ``index.vrt`` (or the configured *vrt_filename*) already exists in
        the data directory it is returned immediately without running
        ``gdalbuildvrt``.

        Returns
        -------
        str
            Absolute path to the VRT file.

        Raises
        ------
        FileNotFoundError
            If no tiles matching *tile_pattern* are found in *data_dir*.
        RuntimeError
            If ``gdalbuildvrt`` exits with a non-zero status code.
        """
        if os.path.exists(self.vrt_path):
            return self.vrt_path

        tiles = sorted(glob.glob(os.path.join(self.data_dir, self.tile_pattern)))
        if not tiles:
            raise FileNotFoundError(
                f"No tiles matching '{self.tile_pattern}' found in "
                f"{self.data_dir!r}.  Place .img files in that directory "
                f"or change tile_pattern."
            )

        self._run_gdalbuildvrt(tiles)
        return self.vrt_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_gdalbuildvrt(self, tiles: list[str]) -> None:
        """Run ``gdalbuildvrt -overwrite <vrt_path> <tiles...>``."""
        cmd = ["gdalbuildvrt", "-overwrite", self.vrt_path] + tiles
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"gdalbuildvrt failed (exit code {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )
