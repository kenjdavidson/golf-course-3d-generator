"""Feature extractor for cloud-native (no-outline) DTM analysis.

Identifies golf-course features directly from raw elevation data without
requiring OpenStreetMap hole-outline geometry.

Two feature types are detected using a **Laplacian of Gaussian (LoG)**
filter (``scipy.ndimage.gaussian_laplace``):

``green / tee`` (plateau regions)
    A LoG filter highlights convex terrain features (local maxima such as
    elevated greens and tee boxes) as strongly **negative** values.  A
    pixel qualifies as a green/tee candidate when:

    * Its LoG response is in the bottom ``slope_percentile`` of the array
      (strongly convex / peaked), **and**
    * Its slope angle is below ``green_slope_max_deg`` (≤ 3° by default),
      confirming it is a *flat* elevated area rather than a steep ridge.

    Connected components smaller than ``min_region_pixels`` are discarded
    as noise (``skimage.measure.label`` + ``regionprops``).

``bunker`` (depression regions)
    A LoG filter returns strongly **positive** values at concave terrain
    features (local minima, i.e. bunker-like pits).  A pixel qualifies as
    a bunker candidate when:

    * Its LoG response is in the top ``slope_percentile`` of the array
      (strongly concave / pit-like), **and**
    * Its elevation is below ``median − 0.5 × std``, confirming the pixel
      sits in a genuine depression relative to the surrounding terrain.

    Small components are discarded with the same connected-component filter.

The Gaussian smoothing controlled by *sigma* suppresses high-frequency
noise (rocks, long grass) before the Laplacian is computed, so ``sigma=2``
corresponds to roughly a 2-pixel (~1 m at 0.5 m/pixel) noise-suppression
radius.

Libraries used
--------------
* **NumPy / SciPy** – ``gaussian_laplace`` and ``gradient``.
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
from scipy.ndimage import gaussian_laplace
from skimage.measure import label as skimage_label, regionprops


class FeatureExtractor:
    """Extract green/tee and bunker masks from a raw elevation grid.

    Parameters
    ----------
    sigma:
        Standard deviation for the Gaussian part of the LoG filter.
        Larger values suppress finer-scale noise.  Default ``2.0``.
    green_slope_max_deg:
        Maximum slope angle (degrees) for a pixel to qualify as a green/tee
        plateau.  Default ``3.0`` (nearly flat).
    slope_percentile:
        Percentile threshold used for both the green (bottom percentile of
        LoG → strongly convex) and bunker (top percentile of LoG → strongly
        concave) candidate selection.  Default ``25``.
    min_region_pixels:
        Minimum connected-component size (pixels) to retain as a feature.
        Components smaller than this are treated as noise.  Default ``10``.
    """

    def __init__(
        self,
        sigma: float = 2.0,
        green_slope_max_deg: float = 3.0,
        slope_percentile: float = 25.0,
        min_region_pixels: int = 10,
    ) -> None:
        self.sigma = sigma
        self.green_slope_max_deg = green_slope_max_deg
        self.slope_percentile = slope_percentile
        self.min_region_pixels = min_region_pixels

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_green_mask(self, elevation: np.ndarray) -> np.ndarray:
        """Return a boolean mask of green/tee plateau regions.

        Uses the Laplacian of Gaussian (LoG) to detect convex terrain
        features (negative LoG response) combined with a slope check to
        confirm the area is flat.

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

        # LoG: negative at convex features (plateaus / greens)
        lap = gaussian_laplace(filled, sigma=self.sigma)
        lap_thresh = float(np.percentile(lap.ravel(), self.slope_percentile))

        # Slope: confirm the candidate is nearly flat.
        # For small angles, gradient_magnitude < tan(angle) is equivalent to
        # arctan(gradient_magnitude) < angle, avoiding an expensive arctan call.
        grad_y, grad_x = np.gradient(filled)
        slope_magnitude = np.hypot(grad_x, grad_y)

        candidate = (lap <= lap_thresh) & (
            slope_magnitude < np.tan(np.radians(self.green_slope_max_deg))
        )
        return self._filter_small_regions(candidate)

    def extract_bunker_mask(self, elevation: np.ndarray) -> np.ndarray:
        """Return a boolean mask of bunker/depression regions.

        Uses the Laplacian of Gaussian (LoG) to detect concave terrain
        features (positive LoG response) combined with an elevation check
        to confirm the area is a genuine depression.

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

        # LoG: positive at concave features (pits / bunkers)
        lap = gaussian_laplace(filled, sigma=self.sigma)
        lap_thresh = float(np.percentile(lap.ravel(), 100 - self.slope_percentile))

        # Elevation: confirm the candidate is below median terrain
        bunker_elev_thresh = median_z - 0.5 * std_z

        candidate = (lap >= lap_thresh) & (filled < bunker_elev_thresh)
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
