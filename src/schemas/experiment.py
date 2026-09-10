"""Experiment schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    status: str = Field(default="created", pattern="^(created|running|completed|failed)$")
    start_time: datetime | None = None
    end_time: datetime | None = None
    metrics: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None


class ExperimentUpdate(BaseModel):
    """Partial update — only the fields explicitly provided are applied."""

    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern="^(created|running|completed|failed)$")
    start_time: datetime | None = None
    end_time: datetime | None = None
    metrics: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    status: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    metrics: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime | None = None
