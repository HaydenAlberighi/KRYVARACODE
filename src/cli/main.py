"""Command-line interface for KRYVARACODE local operations.

Run from the project root, e.g.::

    python -m src.cli init-db
    python -m src.cli create-user --email a@b.c --username alice --password secret123
    python -m src.cli status
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402
from src.db import crud, models  # noqa: E402
from src.db.database import SessionLocal, engine, init_db  # noqa: E402


@click.group()
@click.version_option(version=settings.PROJECT_VERSION, prog_name=settings.APP_NAME)
def cli() -> None:
    """KRYVARACODE local operations."""


@cli.command("init-db")
def init_db_command() -> None:
    """Create all database tables (dev/test bootstrap; prod uses Alembic)."""
    init_db()
    tables = sorted(models.Base.metadata.tables.keys())
    click.echo(f"Database ready at {settings.DATABASE_URL}")
    click.echo(f"Tables: {', '.join(tables)}")


def _open_session():
    return SessionLocal()


@cli.command("create-user")
@click.option("--email", required=True, help="User email address.")
@click.option("--username", required=True, help="Unique username.")
@click.option("--password", required=True, help="Plaintext password (will be hashed).")
@click.option("--full-name", default=None, help="Display name.")
@click.option("--superuser", is_flag=True, default=False, help="Grant superuser flag.")
def create_user_command(
    email: str, username: str, password: str, full_name: Optional[str], superuser: bool
) -> None:
    """Register a new user."""
    db = _open_session()
    try:
        if crud.get_user_by_email(db, email=email) is not None:
            raise click.ClickException(f"Email already registered: {email}")
        if crud.get_user_by_username(db, username=username) is not None:
            raise click.ClickException(f"Username already taken: {username}")
        user = crud.create_user(
            db, email=email, username=username, password=password, full_name=full_name
        )
        if superuser:
            user.is_superuser = True
            db.commit()
            db.refresh(user)
        click.echo(f"Created user id={user.id} username={user.username}")
    finally:
        db.close()


@cli.command("list-users")
@click.option("--limit", default=20, show_default=True, help="Max rows to show.")
def list_users_command(limit: int) -> None:
    """List registered users."""
    db = _open_session()
    try:
        for user in crud.get_users(db, limit=limit):
            click.echo(
                f"{user.id}\t{user.username}\t{user.email}\t"
                f"active={user.is_active}\tsuperuser={user.is_superuser}"
            )
    finally:
        db.close()


def _resolve_actor(db, username: Optional[str]) -> models.User:
    if username:
        user = crud.get_user_by_username(db, username=username)
        if user is None:
            raise click.ClickException(f"User not found: {username}")
        return user
    users = crud.get_users(db, limit=1)
    if not users:
        raise click.ClickException("No users exist yet — run create-user first.")
    return users[0]


@cli.command("upload-dataset")
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Data file (.csv, .parquet, .json).",
)
@click.option("--name", default=None, help="Dataset name (defaults to filename stem).")
@click.option("--description", default=None, help="Dataset description.")
@click.option(
    "--username", default=None, help="Owner username (defaults to first user)."
)
def upload_dataset_command(
    file_path: str,
    name: Optional[str],
    description: Optional[str],
    username: Optional[str],
) -> None:
    """Upload a data file and register it as a dataset."""
    from src.api.data.router import _FORMAT_BY_SUFFIX

    suffix = Path(file_path).suffix.lower()
    file_format = _FORMAT_BY_SUFFIX.get(suffix)
    if file_format is None:
        raise click.ClickException(
            f"Unsupported file format {suffix or 'unknown'}; expected .csv, .parquet or .json"
        )
    dataset_name = ((name or Path(file_path).stem).strip() or "upload")[:100]
    db = _open_session()
    try:
        if crud.get_dataset_by_name(db, name=dataset_name) is not None:
            raise click.ClickException(f"Dataset already exists: {dataset_name}")
        actor = _resolve_actor(db, username)
        from src.schemas import DatasetCreate

        dataset = crud.create_dataset(
            db,
            dataset_data=DatasetCreate(
                name=dataset_name,
                description=description,
                storage_uri=str(Path(file_path).resolve()),
                format=file_format,
            ).model_dump(),
            user_id=actor.id,
        )
        click.echo(f"Registered dataset id={dataset.id} name={dataset.name}")
    finally:
        db.close()


@cli.command("list-datasets")
@click.option("--limit", default=20, show_default=True, help="Max rows to show.")
def list_datasets_command(limit: int) -> None:
    """List registered datasets."""
    db = _open_session()
    try:
        for ds in crud.get_datasets(db, limit=limit):
            click.echo(
                f"{ds.id}\t{ds.name}\t{ds.format}\t{ds.status}\t{ds.storage_uri}"
            )
    finally:
        db.close()


@cli.command("train")
@click.option("--dataset-id", required=True, type=int, help="Dataset to train on.")
@click.option("--target", required=True, help="Target column name.")
@click.option(
    "--experiment", default="cli-train", show_default=True, help="Experiment name."
)
def train_command(dataset_id: int, target: str, experiment: str) -> None:
    """Train a model using a registered dataset."""
    from src.tasks.prediction import train_task

    result = train_task.delay(
        dataset_id=dataset_id, target=target, experiment=experiment, user_id=1
    )
    click.echo(
        f"Training task queued. Task ID: {result.id}. Monitor with: python -m src.cli agent-invoke predict --task-id {result.id}"
    )


@cli.command("status")
def status_command() -> None:
    """Show service version, environment and database health."""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    db = _open_session()
    try:
        counts = {
            "users": len(crud.get_users(db, limit=100000)),
            "datasets": len(crud.get_datasets(db, limit=100000)),
            "models": len(crud.get_model_metadata_list(db, limit=100000)),
            "experiments": len(crud.get_experiments(db, limit=100000)),
        }
    finally:
        db.close()
    click.echo(
        f"{settings.APP_NAME} v{settings.PROJECT_VERSION} env={settings.APP_ENV}"
    )
    click.echo(f"database={'ok' if db_ok else 'unavailable'} ({settings.DATABASE_URL})")
    click.echo(" ".join(f"{k}={v}" for k, v in counts.items()))


@cli.command("serve")
@click.option("--host", default=None, help="Bind host (defaults to settings.HOST).")
@click.option(
    "--port", default=None, type=int, help="Bind port (defaults to settings.PORT)."
)
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
def serve_command(host: Optional[str], port: Optional[int], reload: bool) -> None:
    """Start the API server."""
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=host or settings.HOST,
        port=port or settings.PORT,
        reload=reload,
    )


@cli.command("agent-tools")
def agent_tools_command() -> None:
    """List all registered agent tools."""
    from src.agent.tools import TOOLS

    for tool in TOOLS:
        first_line = tool.description.strip().splitlines()[0]
        click.echo(f"{tool.name}\t{first_line}")


@cli.command("agent-invoke")
@click.argument("name")
@click.option(
    "--args-json",
    default="{}",
    show_default=True,
    help="Tool arguments as a JSON object.",
)
@click.option(
    "--username", default=None, help="Acting username (defaults to anonymous)."
)
def agent_invoke_command(name: str, args_json: str, username: Optional[str]) -> None:
    """Invoke an agent tool by name."""
    from src.agent.tools import invoke_tool

    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid --args-json: {exc}")
    if not isinstance(arguments, dict):
        raise click.ClickException("--args-json must be a JSON object")
    db = _open_session()
    try:
        user = None
        if username:
            user = _resolve_actor(db, username)
        result = invoke_tool(name, arguments, db, user)
        click.echo(json.dumps(result, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    cli()
