"""Factory for creating the appropriate :class:`~src.generators.base.HoleGenerator`.

Selecting a generator
---------------------
The factory inspects whether a ``dtm_dir`` path has been supplied:

* **Local VRT path** – ``dtm_dir`` is not ``None``:
  returns a :class:`~src.generators.vrt_generator.VRTHoleGenerator`.
* **Cloud-native path** – ``dtm_dir`` is ``None``:
  returns an :class:`~src.generators.imageserver_generator.ImageServerHoleGenerator`.

Usage
-----
::

    from src.generators.factory import create_generator

    # Local tile directory
    gen = create_generator(dtm_dir="/data/milton")

    # Ontario ImageServer (no local files)
    gen = create_generator()

    # Then in both cases:
    gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/output/hole")
"""

from __future__ import annotations

from typing import Optional

from .imageserver_generator import ImageServerHoleGenerator
from .vrt_generator import VRTHoleGenerator
from .base import HoleGenerator


def create_generator(
    dtm_dir: Optional[str] = None,
    base_thickness: float = 3.0,
    z_scale: float = 1.5,
    target_size_mm: Optional[float] = None,
) -> HoleGenerator:
    """Return the appropriate :class:`~src.generators.base.HoleGenerator`.

    Parameters
    ----------
    dtm_dir:
        Path to a directory containing DTM tile files.  When ``None``
        (default) the Ontario ArcGIS ImageServer is used.
    base_thickness:
        Solid base depth in metres.
    z_scale:
        Vertical exaggeration factor.
    target_size_mm:
        Optional print-bed rescaling (longest XY → this many mm).

    Returns
    -------
    :class:`~src.generators.vrt_generator.VRTHoleGenerator` when *dtm_dir*
    is provided, otherwise
    :class:`~src.generators.imageserver_generator.ImageServerHoleGenerator`.
    """
    if dtm_dir is not None:
        return VRTHoleGenerator(
            dtm_dir=dtm_dir,
            base_thickness=base_thickness,
            z_scale=z_scale,
            target_size_mm=target_size_mm,
        )
    return ImageServerHoleGenerator(
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
    )
