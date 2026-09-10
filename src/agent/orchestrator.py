"""
Orchestration logic to evaluate event-driven triggers based on AuditLog patterns.
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import AuditLog, ScheduledJob

logger = logging.getLogger(__name__)


class EventEvaluator:
    """
    Evaluates whether a ScheduledJob's trigger_condition is met based on
    recent activity in the AuditLog.
    """

    def evaluate(self, db: Session, job: ScheduledJob) -> bool:
        """
        Check if the job's trigger_condition (if any) is currently satisfied.
        Example conditions: 'tool_fail_count:5' (Trigger if tool fails 5 times)
        """
        condition = job.trigger_condition
        if not condition:
            return False

        try:
            if ":" not in condition:
                logger.warning("Invalid trigger condition format: %s", condition)
                return False

            metric, threshold_str = condition.split(":", 1)
            threshold = int(threshold_str)

            if metric == "tool_fail_count":
                # Count failures of the specific tool associated with this job
                # focusing on the last interval or a reasonable window.
                count = (
                    db.query(func.count(AuditLog.id))
                    .filter(
                        AuditLog.tool_name == job.tool_name, AuditLog.success == False
                    )
                    .scalar()
                )

                return (count or 0) >= threshold

            # Future extensibility: add 'latency_gt:500' or 'success_rate_lt:0.8'

            logger.info("Unsupported metric in trigger condition: %s", metric)
            return False

        except Exception as e:
            logger.error("Error evaluating trigger condition '%s': %s", condition, e)
            return False


event_evaluator = EventEvaluator()
