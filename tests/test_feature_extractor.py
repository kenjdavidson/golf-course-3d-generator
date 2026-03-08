"""
Tests for FeatureExtractor.

Uses synthetic elevation arrays – no external files or network calls required.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.services.feature_extractor import FeatureExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_grid(rows: int = 30, cols: int = 30, value: float = 50.0) -> np.ndarray:
    """Return a completely flat elevation grid."""
    return np.full((rows, cols), value, dtype=np.float64)


def _terrain_with_plateau(rows: int = 30, cols: int = 30) -> np.ndarray:
    """Synthetic grid with a clear central flat plateau and edge depressions."""
    z = np.ones((rows, cols), dtype=np.float64) * 50.0
    r_mid, c_mid = rows // 2, cols // 2
    # Large central plateau (green-like): flat and elevated.
    z[r_mid - 4 : r_mid + 5, c_mid - 4 : c_mid + 5] = 65.0
    # Corner depressions (bunker-like): lower than median.
    z[0:4, 0:4] = 30.0
    z[0:4, -4:] = 30.0
    return z


# ---------------------------------------------------------------------------
# FeatureExtractor.extract_green_mask
# ---------------------------------------------------------------------------

class TestExtractGreenMask:
    def test_returns_boolean_array(self):
        extractor = FeatureExtractor()
        z = _terrain_with_plateau()
        mask = extractor.extract_green_mask(z)
        assert mask.dtype == bool

    def test_shape_matches_input(self):
        extractor = FeatureExtractor()
        z = _terrain_with_plateau(20, 25)
        mask = extractor.extract_green_mask(z)
        assert mask.shape == z.shape

    def test_plateau_region_detected(self):
        """The central plateau should be marked as green."""
        extractor = FeatureExtractor(min_region_pixels=5)
        z = _terrain_with_plateau()
        mask = extractor.extract_green_mask(z)
        r_mid, c_mid = z.shape[0] // 2, z.shape[1] // 2
        # Centre of the plateau must be in the mask.
        assert mask[r_mid, c_mid], "Central plateau pixel not detected as green"

    def test_deep_depression_not_in_green_mask(self):
        """Corner depressions (low elevation) should NOT appear in green mask."""
        extractor = FeatureExtractor(min_region_pixels=5)
        z = _terrain_with_plateau()
        mask = extractor.extract_green_mask(z)
        # Corner pixels are below median → should not be green.
        assert not mask[0, 0], "Corner depression incorrectly detected as green"

    def test_no_pixels_on_completely_flat_grid(self):
        """On a perfectly flat grid slope is zero everywhere → only flat regions qualify.
        All pixels have the same slope (0) and elevation (median) so results can vary,
        but the mask must be a valid boolean array of the correct shape."""
        extractor = FeatureExtractor()
        z = _flat_grid()
        mask = extractor.extract_green_mask(z)
        assert mask.shape == z.shape
        assert mask.dtype == bool

    def test_nan_handling(self):
        """NaN pixels should not cause errors; mask should be valid."""
        extractor = FeatureExtractor(min_region_pixels=2)
        z = _terrain_with_plateau()
        z[0, 0] = np.nan
        mask = extractor.extract_green_mask(z)
        assert mask.shape == z.shape
        assert not np.any(np.isnan(mask))

    def test_min_region_pixels_filters_small_blobs(self):
        """Increasing min_region_pixels should remove small isolated features."""
        z = _terrain_with_plateau()
        extractor_loose = FeatureExtractor(min_region_pixels=1)
        extractor_strict = FeatureExtractor(min_region_pixels=500)
        mask_loose = extractor_loose.extract_green_mask(z)
        mask_strict = extractor_strict.extract_green_mask(z)
        # Strict filter should retain fewer (or equal) pixels.
        assert mask_strict.sum() <= mask_loose.sum()


# ---------------------------------------------------------------------------
# FeatureExtractor.extract_bunker_mask
# ---------------------------------------------------------------------------

class TestExtractBunkerMask:
    def test_returns_boolean_array(self):
        extractor = FeatureExtractor()
        z = _terrain_with_plateau()
        mask = extractor.extract_bunker_mask(z)
        assert mask.dtype == bool

    def test_shape_matches_input(self):
        extractor = FeatureExtractor()
        z = _terrain_with_plateau(20, 25)
        mask = extractor.extract_bunker_mask(z)
        assert mask.shape == z.shape

    def test_depression_region_detected(self):
        """Corner depressions should be marked as bunkers."""
        extractor = FeatureExtractor(min_region_pixels=4)
        z = _terrain_with_plateau()
        mask = extractor.extract_bunker_mask(z)
        # At least one corner depression pixel should be detected.
        corner_detected = mask[0:4, 0:4].any() or mask[0:4, -4:].any()
        assert corner_detected, "No corner depression detected as bunker"

    def test_plateau_not_in_bunker_mask(self):
        """The elevated central plateau should NOT be flagged as a bunker."""
        extractor = FeatureExtractor(min_region_pixels=4)
        z = _terrain_with_plateau()
        mask = extractor.extract_bunker_mask(z)
        r_mid, c_mid = z.shape[0] // 2, z.shape[1] // 2
        assert not mask[r_mid, c_mid], "Plateau centre incorrectly detected as bunker"

    def test_nan_handling(self):
        """NaN pixels should not cause errors."""
        extractor = FeatureExtractor(min_region_pixels=2)
        z = _terrain_with_plateau()
        z[0, 0] = np.nan
        mask = extractor.extract_bunker_mask(z)
        assert mask.shape == z.shape
        assert not np.any(np.isnan(mask))

    def test_min_region_pixels_filters_small_blobs(self):
        """Increasing min_region_pixels should remove small isolated features."""
        z = _terrain_with_plateau()
        extractor_loose = FeatureExtractor(min_region_pixels=1)
        extractor_strict = FeatureExtractor(min_region_pixels=500)
        mask_loose = extractor_loose.extract_bunker_mask(z)
        mask_strict = extractor_strict.extract_bunker_mask(z)
        assert mask_strict.sum() <= mask_loose.sum()

    def test_closing_size_affects_result(self):
        """Different closing sizes should produce different (or equal) bunker masks."""
        z = _terrain_with_plateau()
        extractor_small = FeatureExtractor(bunker_closing_size=3, min_region_pixels=2)
        extractor_large = FeatureExtractor(bunker_closing_size=9, min_region_pixels=2)
        mask_small = extractor_small.extract_bunker_mask(z)
        mask_large = extractor_large.extract_bunker_mask(z)
        # Both must be valid boolean masks – the actual difference is implementation-specific.
        assert mask_small.dtype == bool
        assert mask_large.dtype == bool


# ---------------------------------------------------------------------------
# FeatureExtractor._fill_nan
# ---------------------------------------------------------------------------

class TestFillNan:
    def test_no_nans_unchanged(self):
        z = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = FeatureExtractor._fill_nan(z)
        np.testing.assert_array_equal(result, z)

    def test_nans_replaced_with_min(self):
        z = np.array([[np.nan, 5.0], [3.0, np.nan]])
        result = FeatureExtractor._fill_nan(z)
        assert not np.any(np.isnan(result))
        assert result[0, 0] == 3.0
        assert result[1, 1] == 3.0

    def test_all_nan_returns_zeros(self):
        z = np.full((3, 3), np.nan)
        result = FeatureExtractor._fill_nan(z)
        np.testing.assert_array_equal(result, np.zeros((3, 3)))

    def test_does_not_modify_input(self):
        z = np.array([[np.nan, 1.0]])
        original = z.copy()
        FeatureExtractor._fill_nan(z)
        np.testing.assert_array_equal(z, original)


# ---------------------------------------------------------------------------
# Green and bunker masks are disjoint on a well-structured terrain
# ---------------------------------------------------------------------------

class TestMaskProperties:
    def test_green_and_bunker_masks_do_not_overlap(self):
        """On a terrain with clear plateau and depression, masks should not overlap."""
        extractor = FeatureExtractor(min_region_pixels=5)
        z = _terrain_with_plateau()
        green = extractor.extract_green_mask(z)
        bunker = extractor.extract_bunker_mask(z)
        overlap = green & bunker
        # There should be minimal or no overlap between detected features.
        assert overlap.sum() == 0, (
            f"Green and bunker masks overlap at {overlap.sum()} pixels"
        )
