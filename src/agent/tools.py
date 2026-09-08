"""KRYVARACODE agent tool registry.

This module is the single source of truth for the tools this stack exposes
to LLM agents. Three surfaces consume the same registry:

  - the HTTP agent API        (src/api/agent/router.py)
  - the MCP server            (src/mcp_server.py)
  - the CLI (read-only subset) (src/cli/main.py)

A tool is a named, documented callable with a Pydantic argument model used
for both validation and OpenAI-style JSON Schema generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from src.core.config import settings
from src.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from src.db import crud, models
from src.db.database import engine
from src.schemas.dataset import DatasetCreate, DatasetRead
from src.schemas.experiment import ExperimentCreate, ExperimentRead
from src.schemas.model import ModelCreate, ModelRead
from src.schemas.prediction import PredictionRequest

from src.api.prediction.service import (
    _MLFLOW_AVAILABLE,
    _PANDAS_AVAILABLE,
    prediction_service,
)


# --------------------------------------------------------------------------
# Argument models
# --------------------------------------------------------------------------


class NoArgs(BaseModel):
    """No arguments required."""


class ListArgs(BaseModel):
    """Generic pagination arguments."""

    skip: int = Field(0, ge=0, description="Number of rows to skip")
    limit: int = Field(
        100, ge=1, le=1000, description="Maximum number of rows to return"
    )


class GetDatasetArgs(BaseModel):
    dataset_id: int = Field(..., ge=1, description="Dataset primary key")


class GetModelArgs(BaseModel):
    model_id: int = Field(..., ge=1, description="Model metadata primary key")


class GetModelByNameArgs(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=255, description="Registered model name"
    )
    version: Optional[str] = Field(
        None, description="Model version (defaults to any/None)"
    )


class GetExperimentArgs(BaseModel):
    experiment_id: int = Field(..., ge=1, description="Experiment primary key")


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

Handler = Callable[[BaseModel, Session, Optional[models.User]], Dict[str, Any]]


def _require_user(user: Optional[models.User]) -> int:
    """Return the authenticated user id or raise for user-scoped tools."""
    if user is None:
        raise ForbiddenError("This tool requires an authenticated user")
    return user.id


def system_info(
    _args: NoArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Report service health, version, environment and capability flags."""
    db_status: str = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive
        db_status = f"unavailable: {exc}"
    return {
        "service": settings.APP_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "mlflow_available": bool(_MLFLOW_AVAILABLE),
        "prediction_available": bool(_PANDAS_AVAILABLE),
        "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
    }


def list_datasets(
    args: ListArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    rows = crud.get_datasets(db, skip=args.skip, limit=args.limit)
    return {
        "items": [DatasetRead.model_validate(r).model_dump(mode="json") for r in rows],
        "total": len(rows),
    }


def get_dataset(
    args: GetDatasetArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    row = crud.get_dataset(db, args.dataset_id)
    if row is None:
        raise NotFoundError("Dataset not found")
    return DatasetRead.model_validate(row).model_dump(mode="json")


def create_dataset(
    args: DatasetCreate, db: Session, user: Optional[models.User]
) -> Dict[str, Any]:
    _require_user(user)
    if crud.get_dataset_by_name(db, args.name) is not None:
        raise ConflictError(f"Dataset '{args.name}' already exists")
    row = crud.create_dataset(db, args.model_dump(), _require_user(user))
    return DatasetRead.model_validate(row).model_dump(mode="json")


def list_models(
    args: ListArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    rows = crud.get_model_metadata_list(db, skip=args.skip, limit=args.limit)
    return {
        "items": [ModelRead.model_validate(r).model_dump(mode="json") for r in rows],
        "total": len(rows),
    }


def get_model(
    args: GetModelArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    row = crud.get_model_metadata(db, args.model_id)
    if row is None:
        raise NotFoundError("Model not found")
    return ModelRead.model_validate(row).model_dump(mode="json")


def get_model_by_name(
    args: GetModelByNameArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    row = crud.get_model_metadata_by_name(db, args.name, args.version)
    if row is None:
        raise NotFoundError(f"Model '{args.name}' not found")
    return ModelRead.model_validate(row).model_dump(mode="json")


def register_model(
    args: ModelCreate, db: Session, user: Optional[models.User]
) -> Dict[str, Any]:
    _require_user(user)
    if crud.get_model_metadata_by_name(db, args.name, args.version) is not None:
        raise ConflictError(
            f"Model '{args.name}' version '{args.version}' already registered"
        )
    row = crud.create_model_metadata(db, args.model_dump(), _require_user(user))
    return ModelRead.model_validate(row).model_dump(mode="json")


def list_experiments(
    args: ListArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    rows = crud.get_experiments(db, skip=args.skip, limit=args.limit)
    return {
        "items": [
            ExperimentRead.model_validate(r).model_dump(mode="json") for r in rows
        ],
        "total": len(rows),
    }


def get_experiment(
    args: GetExperimentArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    row = crud.get_experiment(db, args.experiment_id)
    if row is None:
        raise NotFoundError("Experiment not found")
    return ExperimentRead.model_validate(row).model_dump(mode="json")


def create_experiment(
    args: ExperimentCreate, db: Session, user: Optional[models.User]
) -> Dict[str, Any]:
    _require_user(user)
    row = crud.create_experiment(db, args.model_dump(), _require_user(user))
    return ExperimentRead.model_validate(row).model_dump(mode="json")


def predict(
    args: PredictionRequest, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    if not _PANDAS_AVAILABLE:
        raise ServiceUnavailableError(
            "Prediction requires the ML runtime (pandas/numpy/mlflow), which is not installed on this deployment."
        )
    try:
        return prediction_service.predict(args.features)
    except RuntimeError as exc:
        raise ServiceUnavailableError(str(exc)) from exc


def train_model(
    _args: NoArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    raise ServiceUnavailableError(
        "Training pipeline not implemented yet — see src/ml/training.py"
    )


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: type[BaseModel]
    handler: Handler
    requires_user: bool = False


TOOLS: List[Tool] = [
    Tool(
        "system_info",
        "Get service health, version, environment and capability flags (MLflow/prediction availability).",
        NoArgs,
        system_info,
    ),
    Tool(
        "list_datasets",
        "List registered datasets with pagination.",
        ListArgs,
        list_datasets,
    ),
    Tool(
        "get_dataset",
        "Fetch a single dataset by its numeric id.",
        GetDatasetArgs,
        get_dataset,
    ),
    Tool(
        "create_dataset",
        "Register a dataset in the catalog (metadata only, no file upload). Returns the created record.",
        DatasetCreate,
        create_dataset,
        requires_user=True,
    ),
    Tool(
        "list_models",
        "List registered model metadata with pagination.",
        ListArgs,
        list_models,
    ),
    Tool(
        "get_model",
        "Fetch registered model metadata by its numeric id.",
        GetModelArgs,
        get_model,
    ),
    Tool(
        "get_model_by_name",
        "Fetch registered model metadata by name and optional version.",
        GetModelByNameArgs,
        get_model_by_name,
    ),
    Tool(
        "register_model",
        "Register model metadata (name/version/file_path).",
        ModelCreate,
        register_model,
        requires_user=True,
    ),
    Tool(
        "list_experiments",
        "List experiments with pagination.",
        ListArgs,
        list_experiments,
    ),
    Tool(
        "get_experiment",
        "Fetch a single experiment by its numeric id.",
        GetExperimentArgs,
        get_experiment,
    ),
    Tool(
        "create_experiment",
        "Create a new experiment record (status defaults to 'created').",
        ExperimentCreate,
        create_experiment,
        requires_user=True,
    ),
    Tool(
        "predict",
        "Run a prediction with the currently deployed MLflow model. Fails if the ML runtime is unavailable.",
        PredictionRequest,
        predict,
    ),
    Tool(
        "train_model",
        "Trigger a training run. Not implemented yet in this build.",
        NoArgs,
        train_model,
    ),
]

_TOOLS_BY_NAME: Dict[str, Tool] = {tool.name: tool for tool in TOOLS}


def get_tool(name: str) -> Optional[Tool]:
    return _TOOLS_BY_NAME.get(name)


def tool_schema(tool: Tool) -> Dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters.model_json_schema(),
    }


def all_tool_schemas() -> List[Dict[str, Any]]:
    return [tool_schema(tool) for tool in TOOLS]


def invoke_tool(
    name: str, arguments: Dict[str, Any], db: Session, user: Optional[models.User]
) -> Dict[str, Any]:
    """Validate arguments against the tool's model and invoke its handler."""
    tool = get_tool(name)
    if tool is None:
        raise NotFoundError(f"Tool '{name}' not found")
    try:
        parsed = tool.parameters(**arguments)
    except ValidationError as exc:
        raise ValidationFailedError(exc.errors(include_url=False)) from exc
    return tool.handler(parsed, db, user)


__all__ = [
    "Tool",
    "TOOLS",
    "get_tool",
    "tool_schema",
    "all_tool_schemas",
    "invoke_tool",
]
