"""Orchestration layer for KRYVARACODE Omega-Prime.

Event-driven trigger evaluation and coordinator-based multi-agent orchestration.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.models import AuditLog, ScheduledJob

logger = logging.getLogger(__name__)


# -- Event Evaluator ---------------------------------------------------------


class EventEvaluator:
    """Evaluates whether a ScheduledJob's trigger_condition is met based on
    recent activity in the AuditLog."""

    def evaluate(self, db: Session, job: ScheduledJob) -> bool:
        """Check if the job's trigger_condition (if any) is currently satisfied.

        Example conditions: ``tool_fail_count:5`` (trigger if tool fails 5 times).
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
                count = (
                    db.query(func.count(AuditLog.id))
                    .filter(
                        AuditLog.tool_name == job.tool_name,
                        not AuditLog.success,
                    )
                    .scalar()
                )
                return (count or 0) >= threshold

            logger.info("Unsupported metric in trigger condition: %s", metric)
            return False

        except (ValueError, TypeError, SQLAlchemyError) as e:
            logger.error("Error evaluating trigger condition '%s': %s", condition, e)
            return False


event_evaluator = EventEvaluator()


# -- Coordinator-Based Orchestrator -------------------------------------------


class OmegaOrchestrator:
    """Coordinator-based orchestrator that wires message bus, task queue,
    shared state, and agent lifecycle management.

    Provides a high-level API for submitting work, routing tasks to agents,
    and monitoring system health -- all backed by the coordination layer.
    """

    def __init__(
        self,
        coordinator: Any | None = None,
        message_bus: Any | None = None,
        task_queue: Any | None = None,
        shared_state: Any | None = None,
    ) -> None:
        from src.agent.coordination.coordinator import coordinator as _coordinator
        from src.agent.coordination.message_bus import message_bus as _bus
        from src.agent.coordination.shared_state import shared_state as _state
        from src.agent.coordination.task_queue import task_queue as _queue

        self.coordinator = coordinator or _coordinator
        self.bus = message_bus or _bus
        self.queue = task_queue or _queue
        self.state = shared_state or _state

    async def start(self) -> None:
        """Start the coordinator and message bus."""
        await self.coordinator.start()
        await self.bus.start()
        logger.info("OmegaOrchestrator started")

    async def stop(self) -> None:
        """Stop the coordinator and message bus."""
        await self.coordinator.stop()
        await self.bus.stop()
        logger.info("OmegaOrchestrator stopped")

    async def submit_task(
        self,
        task_name: str,
        handler: Any,
        *,
        priority: int = 0,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        timeout: float | None = None,
        dependencies: list[str] | None = None,
    ) -> str:
        """Submit a task to the queue and return the task ID.

        Builds a :class:`QueueTask` and routes it through the coordinator.
        """
        from src.agent.coordination.task_queue import QueueTask

        task = QueueTask(
            name=task_name,
            handler=handler,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            timeout=timeout,
            dependencies=dependencies or [],
        )
        return await self.coordinator.submit_task(task)

    def health_report(self) -> dict[str, Any]:
        """Aggregate health data from coordinator, queue, and shared state."""
        return {
            "coordinator": self.coordinator.stats(),
            "queue": self.queue.stats(),
            "state": self.state.get_stats(),
        }


# Global singleton
omega_orchestrator = OmegaOrchestrator()
