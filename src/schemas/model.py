"""Model metadata schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=5000)
    file_path: str = Field(min_length=1, max_length=500)
    file_size: Optional[int] = Field(default=None, ge=0)
    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    description: Optional[str] = None
    file_path: str
    file_size: Optional[int] = None
    accuracy: Optional[float] = None
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
