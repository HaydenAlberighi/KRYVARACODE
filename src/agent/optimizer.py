"""
Optimization logic to analyze tool performance and identify system bottlenecks.
"""

import logging
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.db.models import AuditLog

logger = logging.getLogger(__name__)


class BottleneckAnalyzer:
    """
    Analyzes AuditLog data to identify slow-performing tools and
    latency trends in the agentic workflow.
    """

    def get_slowest_tools(
        self, db: Session, limit: int = 10, min_duration_ms: float = 100.0
    ) -> list[dict[str, Any]]:
        """
        Identify tools with the highest average duration.
        """
        try:
            # Aggregate average duration per tool
            slowest = (
                db.query(
                    AuditLog.tool_name,
                    func.avg(AuditLog.duration_ms).label("avg_duration"),
                    func.count(AuditLog.id).label("invocation_count"),
                    func.max(AuditLog.duration_ms).label("max_duration"),
                )
                .filter(AuditLog.duration_ms >= min_duration_ms)
                .group_by(AuditLog.tool_name)
                .order_by(desc("avg_duration"))
                .limit(limit)
                .all()
            )

            return [
                {
                    "tool_name": row[0],
                    "avg_duration_ms": float(row[1]),
                    "count": row[2],
                    "max_duration_ms": float(row[3]),
                }
                for row in slowest
            ]
        except Exception as e:
            logger.error(f"Error analyzing bottlenecks: {e}")
            return []

    def get_latency_trend(
        self, db: Session, tool_name: str, limit: int = 100
    ) -> list[tuple[float, float]]:
        """
        Returns a time-series of duration_ms for a specific tool to detect degradation.
        """
        try:
            logs = (
                db.query(AuditLog.created_at, AuditLog.duration_ms)
                .filter(AuditLog.tool_name == tool_name)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
                .all()
            )
            return [(log[0].timestamp(), float(log[1])) for log in logs]
        except Exception as e:
            logger.error(f"Error fetching latency trend for {tool_name}: {e}")
            return []


bottleneck_analyzer = BottleneckAnalyzer()
