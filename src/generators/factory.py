"""Factory for creating the appropriate :class:`~src.generators.base.HoleGenerator`.

Selecting a generator
---------------------
The factory inspects whether a ``dtm_dir`` path has been supplied:

* **Local VRT path** – ``dtm_dir`` is not ``None``:
  returns a :class:`~src.generators.vrt_generator.VRTHoleGenerator`.
* **Cloud-native path** – ``dtm_dir`` is ``None``:
  returns an :class:`~src.generators.imageserver_generator.ImageServerHoleGenerator`.

Customising the pipeline
------------------------
Pass a :class:`~src.processors.base.MeshProcessor` to override the
mesh-building stage, or a :class:`~src.outputs.base.OutputWriter` to
override how meshes are persisted::

    from src.generators.factory import create_generator
    from src.processors.log_processor import LoGMeshProcessor
    from src.outputs.layered_stl_output import LayeredSTLOutput

    gen = create_generator(
        dtm_dir="/data/milton",
        processor=LoGMeshProcessor(z_scale=2.0),
        output_writer=LayeredSTLOutput(),
    )
    gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/output/hole")

Usage
-----
::

    from src.generators.factory import create_generator

    # Local tile directory (gradient processor by default)
    gen = create_generator(dtm_dir="/data/milton")

    # Ontario ImageServer (LoG processor by default)
    gen = create_generator()

    # Then in both cases:
    gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/output/hole")
"""

from __future__ import annotations

from typing import Optional

from .imageserver_generator import ImageServerHoleGenerator
from .vrt_generator import VRTHoleGenerator
from .base import HoleGenerator
from ..outputs.base import OutputWriter
from ..processors.base import MeshProcessor


def create_generator(
    dtm_dir: Optional[str] = None,
    base_thickness: float = 3.0,
    z_scale: float = 1.5,
    target_size_mm: Optional[float] = None,
    processor: Optional[MeshProcessor] = None,
    output_writer: Optional[OutputWriter] = None,
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
    processor:
        :class:`~src.processors.base.MeshProcessor` to use for building
        meshes.  When ``None`` each generator picks its own default
        (:class:`~src.processors.gradient_processor.GradientMeshProcessor`
        for the VRT path,
        :class:`~src.processors.log_processor.LoGMeshProcessor`
        for the cloud path).
    output_writer:
        :class:`~src.outputs.base.OutputWriter` to use for persisting
        meshes.  When ``None`` defaults to
        :class:`~src.outputs.layered_stl_output.LayeredSTLOutput`.

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
            processor=processor,
            output_writer=output_writer,
        )
    return ImageServerHoleGenerator(
        base_thickness=base_thickness,
        z_scale=z_scale,
        target_size_mm=target_size_mm,
        processor=processor,
        output_writer=output_writer,
    )
