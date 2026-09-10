"""Dataset schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    storage_uri: str = Field(min_length=1, max_length=500)
    format: str = Field(default="csv", pattern="^(csv|parquet|json)$")
    row_count: int | None = Field(default=None, ge=0)
    columns: list[str] | None = None


class DatasetUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=5000)
    row_count: int | None = Field(default=None, ge=0)
    columns: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(registered|processing|ready|failed)$")


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    storage_uri: str
    format: str
    row_count: int | None = None
    columns: list[str] | None = None
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime | None = None
