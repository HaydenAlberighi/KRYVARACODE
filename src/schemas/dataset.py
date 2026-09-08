"""Dataset schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=5000)
    storage_uri: str = Field(min_length=1, max_length=500)
    format: str = Field(default="csv", pattern="^(csv|parquet|json)$")
    row_count: Optional[int] = Field(default=None, ge=0)
    columns: Optional[List[str]] = None


class DatasetUpdate(BaseModel):
    description: Optional[str] = Field(default=None, max_length=5000)
    row_count: Optional[int] = Field(default=None, ge=0)
    columns: Optional[List[str]] = None
    status: Optional[str] = Field(
        default=None, pattern="^(registered|processing|ready|failed)$"
    )


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    storage_uri: str
    format: str
    row_count: Optional[int] = None
    columns: Optional[List[str]] = None
    status: str
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
