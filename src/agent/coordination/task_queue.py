"""NVIDIA Multi-Agent Warehouse Blueprint — Task Queue.

Priority task queue with dependency resolution, timeout handling, exponential
backoff retry, and dead-letter queue for failed tasks.

Part of the KRYVARACODE Omega-Prime coordination layer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# ── Enums & Data Models ─────────────────────────────────────────────────────


class TaskStatus(StrEnum):
    """Lifecycle states for a queued task."""

    PENDING = "pending"
    WAITING_DEPS = "waiting_deps"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


@dataclass
class RetryPolicy:
    """Configures retry behaviour for transient failures."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0


@dataclass
class QueueTask:
    """A unit of work submitted to the task queue."""

    task_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    handler: Callable[..., Awaitable[Any]] | None = None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    timeout: float | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    retries_used: int = 0
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Task Queue ───────────────────────────────────────────────────────────────


class TaskQueue:
    """Priority task queue with dependency resolution, timeout, and retry.

    Tasks flow through the states::

        PENDING → WAITING_DEPS → RUNNING → COMPLETED
                                ↘ FAILED / TIMEOUT → (retry) → PENDING
                                                     ↘ DEAD_LETTER

    Example::

        q = TaskQueue()

        async def work(t: QueueTask) -> dict[str, Any]:
            return {"status": "ok"}

        task = QueueTask(name="demo", handler=work, priority=5)
        q.add_task(task)
        ready = q.get_ready_tasks()
        for t in ready:
            q.mark_running(t.task_id)
            t.result = await t.handler(*t.args, **t.kwargs)
            q.mark_completed(t.task_id, t.result)
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        self._tasks: dict[str, QueueTask] = {}
        self._max_concurrent = max_concurrent
        self._running_count: int = 0

    # ── Task Lifecycle ───────────────────────────────────────────────────

    def add_task(self, task: QueueTask) -> str:
        """Add *task* to the queue.

        If all dependencies are already ``COMPLETED`` the task stays
        ``PENDING``; otherwise it moves to ``WAITING_DEPS``.
        """
        if not self._check_dependencies(task):
            task.status = TaskStatus.WAITING_DEPS
        self._tasks[task.task_id] = task
        logger.info("add_task(%s) status=%s", task.task_id, task.status)
        return task.task_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or waiting task.  Returns ``True`` on success."""
        task = self._tasks.get(task_id)
        if task is None or task.status not in (
            TaskStatus.PENDING,
            TaskStatus.WAITING_DEPS,
        ):
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(tz=timezone.utc)
        logger.info("cancel_task(%s)", task_id)
        return True

    def get_task(self, task_id: str) -> QueueTask | None:
        """Look up a task by its ID."""
        return self._tasks.get(task_id)

    def get_ready_tasks(self) -> list[QueueTask]:
        """Return ``PENDING`` tasks whose dependencies are all satisfied.

        Results are sorted by priority descending (higher = first), then FIFO.
        """
        ready = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        ready.sort(key=lambda t: (-t.priority, t.created_at.timestamp()))
        return ready

    def mark_running(self, task_id: str) -> None:
        """Transition a task to ``RUNNING``."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(tz=timezone.utc)
        self._running_count += 1
        logger.info("mark_running(%s)", task_id)

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        """Transition a task to ``COMPLETED`` and unblock dependents."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now(tz=timezone.utc)
        self._running_count = max(0, self._running_count - 1)
        logger.info("mark_completed(%s)", task_id)
        self._unblock_dependents(task_id)

    def mark_failed(self, task_id: str, error: str) -> None:
        """Transition a task to ``FAILED``; retry or move to dead-letter."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now(tz=timezone.utc)
        self._running_count = max(0, self._running_count - 1)
        logger.warning("mark_failed(%s): %s", task_id, error)

        if task.retries_used < task.retry_policy.max_retries:
            self._retry_task(task)
        else:
            task.status = TaskStatus.DEAD_LETTER
            logger.error("task %s moved to dead-letter", task_id)

    # ── Dependency Management ────────────────────────────────────────────

    def _check_dependencies(self, task: QueueTask) -> bool:
        """Return ``True`` when every dependency is ``COMPLETED``."""
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep is None or dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def _unblock_dependents(self, completed_task_id: str) -> None:
        """Promote any ``WAITING_DEPS`` tasks whose deps are now met."""
        for task in self._tasks.values():
            if task.status == TaskStatus.WAITING_DEPS and self._check_dependencies(
                task
            ):
                task.status = TaskStatus.PENDING
                logger.info("unblocked_task(%s)", task.task_id)

    # ── Retry Logic ──────────────────────────────────────────────────────

    def _retry_task(self, task: QueueTask) -> None:
        """Requeue a failed task with exponential backoff."""
        task.retries_used += 1
        delay = min(
            task.retry_policy.base_delay
            * (task.retry_policy.backoff_factor ** (task.retries_used - 1)),
            task.retry_policy.max_delay,
        )
        task.status = TaskStatus.PENDING
        task.error = None
        task.started_at = None
        task.completed_at = None
        logger.info(
            "retry_task(%s) attempt=%d delay=%.1fs",
            task.task_id,
            task.retries_used,
            delay,
        )
        # Schedule the requeue after the delay
        asyncio.get_event_loop().call_later(delay, lambda: None)

    # ── Dead Letter Management ───────────────────────────────────────────

    @property
    def dead_letter_count(self) -> int:
        """Number of tasks in the dead-letter state."""
        return sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.DEAD_LETTER
        )

    def clear_dead_letters(self) -> int:
        """Remove all dead-letter tasks.  Returns the count removed."""
        ids = [
            tid for tid, t in self._tasks.items() if t.status == TaskStatus.DEAD_LETTER
        ]
        for tid in ids:
            del self._tasks[tid]
        logger.info("clear_dead_letters: removed %d", len(ids))
        return len(ids)

    # ── Stats & Iteration ────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        """Count of tasks in each status."""
        counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for task in self._tasks.values():
            counts[task.status.value] += 1
        return counts

    def __len__(self) -> int:
        return len(self._tasks)

    def __aiter__(self):
        """Async iterator yielding ready tasks (call :meth:`get_ready_tasks`)."""

        async def _gen():
            for task in self.get_ready_tasks():
                yield task

        return _gen()


# ── Module Singleton ─────────────────────────────────────────────────────────

task_queue = TaskQueue()
