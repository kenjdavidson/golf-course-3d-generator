"""Mesh processor abstractions for the golf course 3D generation pipeline.

A :class:`MeshProcessor` converts a NumPy elevation array (and its rasterio
affine transform) into a dictionary of named :class:`trimesh.Trimesh` objects
ready for export.  Different implementations can apply different
feature-detection and mesh-construction strategies without modifying the
acquisition or export stages of the pipeline.

Public classes
--------------
* :class:`~src.processors.base.MeshProcessor` – abstract base class.
* :class:`~src.processors.gradient_processor.GradientMeshProcessor` – gradient / threshold approach.
* :class:`~src.processors.log_processor.LoGMeshProcessor` – Laplacian of Gaussian approach.
"""

from .base import MeshProcessor
from .gradient_processor import GradientMeshProcessor
from .log_processor import LoGMeshProcessor

__all__ = ["MeshProcessor", "GradientMeshProcessor", "LoGMeshProcessor"]
