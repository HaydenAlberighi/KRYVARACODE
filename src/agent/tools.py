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

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, text as sql_text
from sqlalchemy.orm import Session

from src.agent.accounts import (
    GitHubIssueCreateArgs,
    GitHubIssueListArgs,
    GitHubPrListArgs,
    account_status,
    github_available,
    github_issue_create,
    github_issue_list,
    github_pr_list,
    github_repo_list,
)
from src.agent.computer import (
    ListDirArgs,
    ProcessKillArgs,
    ReadFileArgs,
    RunShellArgs,
    WriteFileArgs,
    list_dir,
    process_kill,
    process_list,
    read_file,
    run_shell,
    write_file,
)
from src.agent.scheduler import (
    CreateScheduledJobArgs,
    ScheduledJobIdArgs,
    create_scheduled_job,
    delete_scheduled_job,
    list_scheduled_jobs,
    run_scheduled_jobs,
)
from src.api.prediction.service import (
    _MLFLOW_AVAILABLE,
    _PANDAS_AVAILABLE,
    prediction_service,
)
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

# --------------------------------------------------------------------------
# Argument models
# --------------------------------------------------------------------------


class NoArgs(BaseModel):
    """No arguments required."""

    model_config = ConfigDict(extra="forbid")


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

ArgsT = TypeVar("ArgsT", bound=BaseModel)


def _require_user(user: Optional[models.User]) -> int:
    """Return the authenticated user id or raise for user-scoped tools."""
    if user is None:
        raise ForbiddenError("This tool requires an authenticated user")
    return user.id


def system_info(
    _args: NoArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Report service health, version, environment and capability flags."""
    db_status: str = "ok"
    try:
        db.execute(sql_text("SELECT 1"))
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
    total = db.query(func.count(models.Dataset.id)).scalar() or 0
    return {
        "items": [DatasetRead.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
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
    user_id = _require_user(user)
    if crud.get_dataset_by_name(db, args.name) is not None:
        raise ConflictError(f"Dataset '{args.name}' already exists")
    row = crud.create_dataset(db, args.model_dump(), user_id)
    return DatasetRead.model_validate(row).model_dump(mode="json")


def list_models(
    args: ListArgs, db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    rows = crud.get_model_metadata_list(db, skip=args.skip, limit=args.limit)
    total = db.query(func.count(models.ModelMetadata.id)).scalar() or 0
    return {
        "items": [ModelRead.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
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
    total = db.query(func.count(models.Experiment.id)).scalar() or 0
    return {
        "items": [
            ExperimentRead.model_validate(r).model_dump(mode="json") for r in rows
        ],
        "total": total,
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
class Tool(Generic[ArgsT]):
    name: str
    description: str
    parameters: type[ArgsT]
    handler: Callable[[ArgsT, Session, Optional[models.User]], Dict[str, Any]]
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
    Tool(
        "run_shell",
        "Execute a single shell command on the host (no pipes, redirects, or "
        "metacharacters). Blocked destructive patterns are rejected; output is "
        "truncated. Filesystem writes stay inside the tool.",
        RunShellArgs,
        run_shell,
    ),
    Tool(
        "read_file",
        "Read a text file inside the allowed roots (project tree, OS temp dir, AGENT_FILE_ROOTS).",
        ReadFileArgs,
        read_file,
    ),
    Tool(
        "write_file",
        "Write text to a file inside the allowed roots, creating parent dirs.",
        WriteFileArgs,
        write_file,
    ),
    Tool(
        "list_dir",
        "List directory entries inside the allowed roots.",
        ListDirArgs,
        list_dir,
    ),
    Tool(
        "process_list",
        "List running host processes (pid and name).",
        NoArgs,
        process_list,
    ),
    Tool(
        "process_kill",
        "Force-terminate a process by pid. System PIDs and the agent itself are refused.",
        ProcessKillArgs,
        process_kill,
    ),
    Tool(
        "account_status",
        "Report which account integrations are live (GitHub via gh CLI, Gmail setup path).",
        NoArgs,
        account_status,
    ),
    Tool(
        "create_scheduled_job",
        "Register a recurring tool invocation run when its interval elapses.",
        CreateScheduledJobArgs,
        create_scheduled_job,
    ),
    Tool(
        "list_scheduled_jobs",
        "List scheduled jobs with pagination.",
        ListArgs,
        list_scheduled_jobs,
    ),
    Tool(
        "run_scheduled_jobs",
        "Execute all due scheduled jobs now and report per-job outcomes.",
        NoArgs,
        run_scheduled_jobs,
    ),
    Tool(
        "delete_scheduled_job",
        "Delete a scheduled job by id.",
        ScheduledJobIdArgs,
        delete_scheduled_job,
    ),
]

if github_available():
    TOOLS.extend(
        [
            Tool(
                "github_repo_list",
                "List GitHub repositories visible to the authenticated user.",
                ListArgs,
                github_repo_list,
            ),
            Tool(
                "github_issue_list",
                "List issues for a repository.",
                GitHubIssueListArgs,
                github_issue_list,
            ),
            Tool(
                "github_issue_create",
                "Create a GitHub issue in a repository.",
                GitHubIssueCreateArgs,
                github_issue_create,
            ),
            Tool(
                "github_pr_list",
                "List pull requests for a repository.",
                GitHubPrListArgs,
                github_pr_list,
            ),
        ]
    )

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


def _write_audit(
    db: Session,
    name: str,
    arguments: Dict[str, Any],
    user: Optional[models.User],
    success: bool,
    error: Optional[str],
    duration_ms: float,
) -> None:
    try:
        try:
            arguments_json: Optional[str] = json.dumps(arguments, default=str)[:4000]
        except (TypeError, ValueError):
            arguments_json = None
        crud.create_audit_entry(
            db,
            tool_name=name,
            user_id=user.id if user is not None else None,
            arguments_json=arguments_json,
            success=success,
            error=error[:2000] if error else None,
            duration_ms=duration_ms,
        )
    except Exception:
        pass


def invoke_tool(
    name: str, arguments: Dict[str, Any], db: Session, user: Optional[models.User]
) -> Dict[str, Any]:
    """Validate arguments against the tool's model and invoke its handler.

    Every invocation is timed and audit-logged; audit failures never break
    tool execution.
    """
    tool = get_tool(name)
    if tool is None:
        raise NotFoundError(f"Tool '{name}' not found")
    start = time.perf_counter()
    try:
        parsed = tool.parameters(**arguments)
    except ValidationError as exc:
        _write_audit(
            db,
            name,
            arguments,
            user,
            False,
            f"ValidationError: {exc}",
            (time.perf_counter() - start) * 1000.0,
        )
        raise ValidationFailedError(
            "Tool arguments failed validation",
            extra={"errors": exc.errors(include_url=False)},
        ) from exc
    try:
        result = tool.handler(parsed, db, user)
    except Exception as exc:
        _write_audit(
            db,
            name,
            arguments,
            user,
            False,
            f"{type(exc).__name__}: {exc}",
            (time.perf_counter() - start) * 1000.0,
        )
        raise
    _write_audit(
        db,
        name,
        arguments,
        user,
        True,
        None,
        (time.perf_counter() - start) * 1000.0,
    )
    return result


__all__ = [
    "Tool",
    "TOOLS",
    "get_tool",
    "tool_schema",
    "all_tool_schemas",
    "invoke_tool",
]
