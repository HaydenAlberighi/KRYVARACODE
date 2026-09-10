"""Model metadata schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=5000)
    file_path: str = Field(min_length=1, max_length=500)
    file_size: int | None = Field(default=None, ge=0)
    accuracy: float | None = Field(default=None, ge=0.0, le=1.0)


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    description: str | None = None
    file_path: str
    file_size: int | None = None
    accuracy: float | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime | None = None
