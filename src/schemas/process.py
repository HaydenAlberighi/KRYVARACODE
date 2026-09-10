"""Schemas for the data processing pipeline (stub) endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProcessRequest(BaseModel):
    """Payload accepted by the data processing stub endpoint."""

    model_config = ConfigDict(extra="forbid")

    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Incoming data to be processed by the pipeline.",
        min_length=1,
        examples=[
            {"user_id": 123, "event": "login", "timestamp": "2023-01-01T00:00:00Z"}
        ],
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline options (e.g. format, batch size).",
        examples=[{"batch_size": 100, "format": "parquet"}],
    )


class ProcessResponse(BaseModel):
    """Acknowledgment returned by the processing stub.

    The actual pipeline (validation, transformation, storage) is not
    implemented yet; this contract documents what it will eventually return.
    """

    status: str
    processed_at: datetime
    processed_by: Optional[str] = None
    message: str
