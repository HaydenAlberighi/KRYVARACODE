"""Proactive half: DB-backed interval jobs executed on trigger.

There is no background thread in the API process (keeps tests and sqlite
predictable). Proactive operation happens when something triggers
``run_scheduled_jobs``: the agent itself, the ``agent-invoke`` CLI command,
or an external cron / Task Scheduler entry. Each run only executes jobs
whose interval has elapsed since ``last_run_at`` (``None`` means due now).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.agent.orchestrator import event_evaluator
from src.core.exceptions import ConflictError, NotFoundError
from src.db import crud, models

if TYPE_CHECKING:  # import-time cycle with tools.py; types only
    from src.agent.tools import ListArgs


class CreateScheduledJobArgs(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    tool_name: str = Field(..., min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    interval_seconds: int = Field(3600, ge=1, le=2592000)
    enabled: bool = Field(True)


class ScheduledJobIdArgs(BaseModel):
    job_id: int = Field(..., ge=1)


class ScheduledJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tool_name: str
    arguments: dict[str, Any] | None = None
    interval_seconds: int
    enabled: bool
    last_run_at: datetime | None = None
    last_status: str | None = None
    created_at: datetime


def _serialize(job: models.ScheduledJob) -> dict[str, Any]:
    return ScheduledJobRead.model_validate(job).model_dump(mode="json")


def create_scheduled_job(
    args: CreateScheduledJobArgs, db: Session, user: models.User | None
) -> dict[str, Any]:
    """Register a recurring tool invocation."""
    from src.agent import tools as registry  # lazy: avoids tools<->scheduler cycle

    if registry.get_tool(args.tool_name) is None:
        raise NotFoundError(f"Unknown tool '{args.tool_name}'")
    if crud.get_scheduled_job_by_name(db, args.name) is not None:
        raise ConflictError(f"Scheduled job '{args.name}' already exists")
    row = crud.create_scheduled_job(
        db,
        {
            "name": args.name,
            "tool_name": args.tool_name,
            "arguments": args.arguments,
            "interval_seconds": args.interval_seconds,
            "enabled": args.enabled,
        },
        user.id if user is not None else None,
    )
    return _serialize(row)


def list_scheduled_jobs(
    args: ListArgs, db: Session, _user: models.User | None
) -> dict[str, Any]:
    """List scheduled jobs."""
    rows = crud.list_scheduled_jobs(db, skip=args.skip, limit=args.limit)
    return {"items": [_serialize(r) for r in rows], "total": len(rows)}


def delete_scheduled_job(
    args: ScheduledJobIdArgs, db: Session, _user: models.User | None
) -> dict[str, Any]:
    """Delete a scheduled job by id."""
    if not crud.delete_scheduled_job(db, args.job_id):
        raise NotFoundError("Scheduled job not found")
    return {"detail": "Scheduled job deleted"}


def run_due_jobs(db: Session, user: models.User | None) -> list[dict[str, Any]]:
    """Execute enabled jobs due by interval or event trigger."""
    from src.agent.tools import invoke_tool  # lazy: avoids tools<->scheduler cycle

    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    for job in crud.list_scheduled_jobs(db, limit=1000):
        if not job.enabled:
            continue

        due_by_interval = False
        last = job.last_run_at
        if last is None:
            due_by_interval = True
        else:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() >= job.interval_seconds:
                due_by_interval = True

        due_by_event = event_evaluator.evaluate(db, job)

        if not (due_by_interval or due_by_event):
            continue

        try:
            invoke_tool(job.tool_name, job.arguments or {}, db, user)
            status = "success"
        except Exception as exc:
            status = f"failed: {type(exc).__name__}: {exc}"[:500]

        crud.update_scheduled_job_run(db, job.id, status, now)
        results.append(
            {
                "job_id": job.id,
                "name": job.name,
                "tool_name": job.tool_name,
                "status": status,
                "trigger": (
                    "event" if due_by_event and not due_by_interval else "interval"
                ),
            }
        )
    return results


def run_scheduled_jobs(
    _args: object, db: Session, user: models.User | None
) -> dict[str, Any]:
    """Trigger execution of all due scheduled jobs now."""
    ran = run_due_jobs(db, user)
    return {"jobs_run": ran, "count": len(ran)}
