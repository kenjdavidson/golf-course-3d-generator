"""Feature extractor for cloud-native (no-outline) DTM analysis.

Identifies golf-course features directly from raw elevation data without
requiring OpenStreetMap hole-outline geometry.

Two feature types are detected:

``green / tee`` (plateau regions)
    Contiguous flat areas at or above the median elevation.  Flatness is
    measured by the gradient magnitude; only pixels below the
    ``slope_percentile`` threshold are considered candidates.  Connected
    components smaller than ``min_region_pixels`` are discarded as noise.

``bunker`` (depression regions)
    Local minima revealed by a morphological *bottom-hat* transform
    (grey closing − original).  Only depressions that also fall below
    ``median − 0.5 × std`` are retained.  Again, tiny components are
    filtered out.

Libraries used:

* **NumPy / SciPy** – gradient computation and morphological transforms.
* **scikit-image** (``skimage.measure``) – connected-component labelling
  and region-property filtering.

Usage
-----
::

    from src.services.feature_extractor import FeatureExtractor

    extractor = FeatureExtractor()
    green_mask  = extractor.extract_green_mask(elevation)
    bunker_mask = extractor.extract_bunker_mask(elevation)
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import grey_closing
from skimage.measure import label as skimage_label, regionprops


class FeatureExtractor:
    """Extract green/tee and bunker masks from a raw elevation grid.

    Parameters
    ----------
    slope_percentile:
        Percentile of the slope-magnitude distribution below which a pixel
        qualifies as "flat" (green/tee candidate).  Default ``25``.
    min_region_pixels:
        Minimum connected-component size (pixels) to retain as a feature.
        Components smaller than this are treated as noise.  Default ``10``.
    bunker_closing_size:
        Side length (pixels) of the square structuring element used in the
        morphological grey closing for the bottom-hat transform.  Default ``5``.
    """

    def __init__(
        self,
        slope_percentile: float = 25.0,
        min_region_pixels: int = 10,
        bunker_closing_size: int = 5,
    ) -> None:
        self.slope_percentile = slope_percentile
        self.min_region_pixels = min_region_pixels
        self.bunker_closing_size = bunker_closing_size

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_green_mask(self, elevation: np.ndarray) -> np.ndarray:
        """Return a boolean mask of green/tee plateau regions.

        Detects contiguous flat areas at or above the median elevation using
        gradient-magnitude thresholding and connected-component labelling
        (``skimage.measure.label``).

        Parameters
        ----------
        elevation:
            2-D float array of elevation values.  ``np.nan`` pixels are
            treated as the minimum valid elevation.

        Returns
        -------
        np.ndarray
            Boolean mask of the same shape as *elevation*.  ``True`` where
            a pixel belongs to a green/tee plateau region.
        """
        filled = self._fill_nan(elevation)
        median_z = float(np.median(filled))

        grad_y, grad_x = np.gradient(filled)
        slope = np.sqrt(grad_x ** 2 + grad_y ** 2)
        low_slope_thresh = float(np.percentile(slope.ravel(), self.slope_percentile))

        candidate = (slope <= low_slope_thresh) & (filled >= median_z)
        return self._filter_small_regions(candidate)

    def extract_bunker_mask(self, elevation: np.ndarray) -> np.ndarray:
        """Return a boolean mask of bunker/depression regions.

        Uses a morphological *bottom-hat* transform (``grey_closing −
        original``) to highlight local minima, then further filters by
        requiring the pixel elevation to be below ``median − 0.5 × std``.
        Connected components are labelled and small ones removed.

        Parameters
        ----------
        elevation:
            2-D float array of elevation values.  ``np.nan`` pixels are
            treated as the minimum valid elevation.

        Returns
        -------
        np.ndarray
            Boolean mask of the same shape as *elevation*.  ``True`` where
            a pixel belongs to a bunker/depression region.
        """
        filled = self._fill_nan(elevation)
        median_z = float(np.median(filled))
        std_z = float(np.std(filled))

        s = self.bunker_closing_size
        closed = grey_closing(filled, size=(s, s))
        bottom_hat = closed - filled

        depth_thresh = float(np.percentile(bottom_hat.ravel(), 75))
        bunker_thresh = median_z - 0.5 * std_z
        candidate = (bottom_hat >= depth_thresh) & (filled < bunker_thresh)
        return self._filter_small_regions(candidate)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_small_regions(self, mask: np.ndarray) -> np.ndarray:
        """Remove connected components smaller than ``min_region_pixels``."""
        labeled = skimage_label(mask)
        result = np.zeros_like(mask, dtype=bool)
        for region in regionprops(labeled):
            if region.area >= self.min_region_pixels:
                result[labeled == region.label] = True
        return result

    @staticmethod
    def _fill_nan(elevation: np.ndarray) -> np.ndarray:
        """Replace NaN values with the minimum valid elevation."""
        arr = elevation.copy()
        if np.any(np.isnan(arr)):
            min_val = float(np.nanmin(arr)) if not np.all(np.isnan(arr)) else 0.0
            arr = np.where(np.isnan(arr), min_val, arr)
        return arr
