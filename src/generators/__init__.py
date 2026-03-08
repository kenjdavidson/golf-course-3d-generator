"""Generators package – OOP pipeline for 3D hole model generation.

Each generator implements a full acquisition → segmentation → mesh-build →
export workflow for a specific elevation-data source.

Usage
-----
::

    from src.generators.factory import create_generator

    gen = create_generator(dtm_dir="/data/milton", base_thickness=3.0)
    gen.generate(lat=43.5, lon=-79.8, buffer_m=50, output_path="/output/hole")
"""

from .base import HoleGenerator
from .vrt_generator import VRTHoleGenerator
from .imageserver_generator import ImageServerHoleGenerator
from .factory import create_generator

__all__ = [
    "HoleGenerator",
    "VRTHoleGenerator",
    "ImageServerHoleGenerator",
    "create_generator",
]
