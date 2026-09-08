"""Schemas for the data processing pipeline (stub) endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Payload accepted by the data processing stub endpoint."""

    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Incoming data to be processed by the pipeline.",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline options (e.g. format, batch size).",
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
