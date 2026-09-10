"""
Monitoring service to detect drift and trigger retraining.
"""

import logging
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from src.db.models import PredictionLog
from src.ml.monitoring import analyze_feature_drift

logger = logging.getLogger(__name__)


class MonitoringService:
    def __init__(self, drift_threshold: float = 0.05):
        self.drift_threshold = drift_threshold

    def check_for_drift(
        self,
        db: Session,
        feature_names: List[str],
        reference_data: Dict[str, List[float]],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Analyzes recent predictions from PredictionLog and compares them to reference data.

        Returns:
            (is_drifted, drift_report)
        """
        # Fetch the most recent predictions for the analysis window (e.g., last 1000 logs)
        logs = (
            db.query(PredictionLog)
            .order_by(PredictionLog.created_at.desc())
            .limit(1000)
            .all()
        )

        if not logs:
            logger.warning("No prediction logs available for drift analysis.")
            return False, {}

        # Extract current distribution of features from logs
        current_data = {name: [] for name in feature_names}
        for log in logs:
            for name in feature_names:
                val = log.features.get(name)
                if val is not None:
                    current_data[name].append(float(val))

        # Run drift analysis
        drift_report = analyze_feature_drift(
            reference_data=reference_data,
            current_data=current_data,
            threshold=self.drift_threshold,
        )

        # Determine if any critical feature has drifted
        is_drifted = any(stats["is_drifted"] for stats in drift_report.values())

        return is_drifted, drift_report


monitoring_service = MonitoringService()
