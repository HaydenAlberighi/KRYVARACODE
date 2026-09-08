"""Agent tool endpoints — expose the KRYVARACODE tool registry to LLM agents.

GET  /agent/tools            -> OpenAI-style tool schemas
POST /agent/tools/{name}/invoke  -> execute a tool with validated arguments
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.agent.tools import all_tool_schemas, invoke_tool as registry_invoke
from src.api.deps import get_current_active_user, get_db
from src.db import models

router = APIRouter(prefix="/agent", tags=["agent"])


class ToolDescription(BaseModel):
    """Schema of one callable tool in OpenAI function-calling format."""

    name: str
    description: str
    parameters: Dict[str, Any]


class ToolInvokeRequest(BaseModel):
    """Body for tool invocation."""

    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments validated against the tool's parameter schema",
    )


@router.get("/tools", response_model=List[ToolDescription])
def list_tools(
    _current_user: models.User = Depends(get_current_active_user),
) -> List[ToolDescription]:
    return [ToolDescription(**schema) for schema in all_tool_schemas()]


@router.post("/tools/{name}/invoke", response_model=Dict[str, Any])
def invoke_tool(
    name: str,
    request: ToolInvokeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return registry_invoke(name, request.arguments, db, current_user)


__all__ = ["router"]
