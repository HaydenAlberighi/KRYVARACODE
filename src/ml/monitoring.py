"""
ML Monitoring utility for KRYVARACODE.
Provides tools to detect feature drift and performance degradation.
"""

import logging
from typing import Any, Dict, List, Tuple

from scipy.stats import ks_2samp

logger = logging.getLogger(__name__)


def compute_drift(
    reference_distribution: List[float],
    current_distribution: List[float],
    threshold: float = 0.05,
) -> Tuple[float, bool]:
    """
    Compute the Kolmogorov-Smirnov (KS) test for feature drift.

    Returns:
        (p_value, is_drifted): p_value from KS test and boolean indicating if drift occurred.
    """
    try:
        # ks_2samp returns (statistic, pvalue)
        statistic, p_value = ks_2samp(reference_distribution, current_distribution)

        # If p-value is below threshold, distributions are significantly different (drifted)
        is_drifted = p_value < threshold

        return p_value, is_drifted
    except Exception as e:
        logger.error(f"Error computing drift: {e}")
        return 1.0, False


def analyze_feature_drift(
    reference_data: Dict[str, List[float]],
    current_data: Dict[str, List[float]],
    threshold: float = 0.05,
) -> Dict[str, Dict[str, Any]]:
    """
    Analyze drift across multiple features.
    """
    drift_report = {}

    for feature_name, ref_values in reference_data.items():
        if feature_name not in current_data:
            logger.warning(
                f"Feature {feature_name} missing from current data. Skipping."
            )
            continue

        curr_values = current_data[feature_name]
        p_val, drifted = compute_drift(ref_values, curr_values, threshold)

        drift_report[feature_name] = {"p_value": p_val, "is_drifted": drifted}

    return drift_report
