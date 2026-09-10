"""
CRUD operations for KRYVARACODE AI System Stack.

All functions take an explicit ``Session`` so they stay testable with any
DB engine. HTTP-specific concerns (auth, pagination parsing) live in the
routers, not here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from src.core.exceptions import ValidationFailedError
from src.core.security import get_password_hash, hash_reset_token, verify_password
from src.db import models


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def get_user(db: Session, user_id: int) -> models.User | None:
    """Get a user by ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_with_items(db: Session, user_id: int) -> models.User | None:
    """Get a user with their items eagerly loaded (avoids the N+1 query pattern)."""
    return db.query(models.User).options(joinedload(models.User.items)).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> models.User | None:
    """Get a user by email."""
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str) -> models.User | None:
    """Get a user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[models.User]:
    """Get multiple users."""
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(
    db: Session,
    email: str,
    username: str,
    password: str,
    full_name: str | None = None,
) -> models.User:
    """Create a new user with a hashed password."""
    hashed_password = get_password_hash(password)
    db_user = models.User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(
    db: Session,
    user_id: int,
    is_verified: bool | None = None,
    failed_login_attempts: int | None = None,
    lock_until: datetime | None = None,
    password_reset_token: str | None = None,
    password_reset_expires: datetime | None = None,
) -> models.User | None:
    """Update user fields (verification status, lockout, reset token).

    A plaintext reset token is stored as its SHA-256 digest at rest; the
    legacy ``password_reset_token`` column is no longer populated.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    if is_verified is not None:
        user.is_verified = is_verified
    if failed_login_attempts is not None:
        user.failed_login_attempts = failed_login_attempts
    if lock_until is not None:
        user.lock_until = lock_until
    if password_reset_token is not None:
        user.hashed_reset_token = hash_reset_token(password_reset_token)
        # Legacy plaintext column: kept for API compatibility, never written.
        user.password_reset_token = None
    if password_reset_expires is not None:
        user.password_reset_expires = password_reset_expires
    db.commit()
    db.refresh(user)
    return user


def clear_reset_token(db: Session, user_id: int) -> models.User | None:
    """Invalidate any active password-reset token for the user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    user.hashed_reset_token = None
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user_id: int, new_password: str) -> models.User | None:
    """Set a new password, rejecting reuse of the current password.

    The new password must already pass the policy validation performed by
    the caller; this additionally rejects a no-op change that matches the
    current hash (password-reuse prevention). Any outstanding reset token
    is invalidated on success.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    if verify_password(new_password, user.hashed_password):
        raise ValidationFailedError("New password must be different from the current password")
    user.hashed_password = get_password_hash(new_password)
    user.hashed_reset_token = None
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> models.User | None:
    """Authenticate a user by username + password.

    Returns the user on success, ``None`` when credentials are invalid.
    Also checks lockout status and resets failed attempts on success.
    """
    user = get_user_by_username(db, username)
    if not user:
        return None
    # Check if account is locked
    lock_until = user.lock_until
    if lock_until is not None:
        if lock_until.tzinfo is None:
            # SQLite returns naive datetimes for DateTime columns; treat as UTC.
            lock_until = lock_until.replace(tzinfo=UTC)
        if lock_until > datetime.now(UTC):
            return None  # Account is locked
    if not verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        # Lock account after 5 failed attempts for 30 minutes
        if user.failed_login_attempts >= 5:
            user.lock_until = datetime.now(UTC) + timedelta(minutes=30)
        db.commit()
        return None
    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.lock_until = None
    db.commit()
    return user


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
def get_items(db: Session, skip: int = 0, limit: int = 100) -> list[models.Item]:
    """Get multiple items."""
    return db.query(models.Item).offset(skip).limit(limit).all()


def get_item(db: Session, item_id: int) -> models.Item | None:
    """Get an item by ID."""
    return db.query(models.Item).filter(models.Item.id == item_id).first()


def create_user_item(db: Session, item: dict, user_id: int) -> models.Item:
    """Create an item for a user."""
    db_item = models.Item(**item, owner_id=user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, item_id: int) -> models.Item | None:
    """Delete an item by ID. Returns the deleted row, or None if not found."""
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        return None
    db.delete(item)
    db.commit()
    return item


# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------
def get_model_metadata(db: Session, model_id: int) -> models.ModelMetadata | None:
    """Get model metadata by ID."""
    return db.query(models.ModelMetadata).filter(models.ModelMetadata.id == model_id).first()


def get_model_metadata_by_name(db: Session, name: str, version: str | None = None) -> models.ModelMetadata | None:
    """Get model metadata by name and optionally version."""
    query = db.query(models.ModelMetadata).filter(models.ModelMetadata.name == name)
    if version:
        query = query.filter(models.ModelMetadata.version == version)
    return query.first()


def get_model_metadata_list(db: Session, skip: int = 0, limit: int = 100) -> list[models.ModelMetadata]:
    """Get multiple model metadata entries."""
    return db.query(models.ModelMetadata).offset(skip).limit(limit).all()


def create_model_metadata(db: Session, model_data: dict, user_id: int) -> models.ModelMetadata:
    """Create model metadata."""
    db_model = models.ModelMetadata(**model_data, created_by=user_id)
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


def delete_model_metadata(db: Session, model_id: int) -> models.ModelMetadata | None:
    """Delete model metadata by ID. Returns the deleted row, or None if not found."""
    model = db.query(models.ModelMetadata).filter(models.ModelMetadata.id == model_id).first()
    if not model:
        return None
    db.delete(model)
    db.commit()
    return model


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------
def get_experiment(db: Session, experiment_id: int) -> models.Experiment | None:
    """Get an experiment by ID."""
    return db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()


def get_experiments(db: Session, skip: int = 0, limit: int = 100) -> list[models.Experiment]:
    """Get multiple experiments."""
    return db.query(models.Experiment).offset(skip).limit(limit).all()


def create_experiment(db: Session, experiment_data: dict, user_id: int) -> models.Experiment:
    """Create an experiment."""
    db_experiment = models.Experiment(**experiment_data, created_by=user_id)
    db.add(db_experiment)
    db.commit()
    db.refresh(db_experiment)
    return db_experiment


def update_experiment(db: Session, experiment_id: int, experiment_data: dict) -> models.Experiment | None:
    """Partially update an experiment. ``None`` values are skipped.

    Returns ``None`` when the experiment does not exist.
    """
    db_experiment = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    if not db_experiment:
        return None
    for field, value in experiment_data.items():
        if value is not None:
            setattr(db_experiment, field, value)
    db.commit()
    db.refresh(db_experiment)
    return db_experiment


def delete_experiment(db: Session, experiment_id: int) -> models.Experiment | None:
    """Delete an experiment by ID. Returns the deleted row, or None if not found."""
    experiment = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    if not experiment:
        return None
    db.delete(experiment)
    db.commit()
    return experiment


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------
def get_dataset(db: Session, dataset_id: int) -> models.Dataset | None:
    """Get a dataset by ID."""
    return db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()


def get_dataset_by_name(db: Session, name: str) -> models.Dataset | None:
    """Get a dataset by name (names are unique per workspace)."""
    return db.query(models.Dataset).filter(models.Dataset.name == name).first()


def get_datasets(db: Session, skip: int = 0, limit: int = 100) -> list[models.Dataset]:
    """Get multiple datasets."""
    return db.query(models.Dataset).offset(skip).limit(limit).all()


def create_dataset(db: Session, dataset_data: dict, user_id: int) -> models.Dataset:
    """Create a dataset."""
    db_dataset = models.Dataset(**dataset_data, created_by=user_id)
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


def update_dataset(db: Session, dataset_id: int, dataset_data: dict) -> models.Dataset | None:
    """Partially update a dataset. ``None`` values are skipped.

    Returns ``None`` when the dataset does not exist.
    """
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not db_dataset:
        return None
    for field, value in dataset_data.items():
        if value is not None:
            setattr(db_dataset, field, value)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


def delete_dataset(db: Session, dataset_id: int) -> models.Dataset | None:
    """Delete a dataset by ID. Returns the deleted row, or None if not found."""
    dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not dataset:
        return None
    db.delete(dataset)
    db.commit()
    return dataset


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def create_audit_entry(
    db: Session,
    tool_name: str,
    user_id: int | None,
    arguments_json: str | None,
    success: bool,
    error: str | None,
    duration_ms: float | None,
) -> models.AuditLog:
    """Append one tool-invocation audit record."""
    entry = models.AuditLog(
        tool_name=tool_name,
        user_id=user_id,
        arguments=arguments_json,
        success=success,
        error=error,
        duration_ms=duration_ms,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_entries(db: Session, skip: int = 0, limit: int = 100) -> list[models.AuditLog]:
    """Get audit entries, newest first."""
    return db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------
def get_scheduled_job(db: Session, job_id: int) -> models.ScheduledJob | None:
    """Get a scheduled job by ID."""
    return db.query(models.ScheduledJob).filter(models.ScheduledJob.id == job_id).first()


def get_scheduled_job_by_name(db: Session, name: str) -> models.ScheduledJob | None:
    """Get a scheduled job by name."""
    return db.query(models.ScheduledJob).filter(models.ScheduledJob.name == name).first()


def list_scheduled_jobs(db: Session, skip: int = 0, limit: int = 100) -> list[models.ScheduledJob]:
    """Get multiple scheduled jobs."""
    return db.query(models.ScheduledJob).offset(skip).limit(limit).all()


def create_scheduled_job(db: Session, job_data: dict, user_id: int | None) -> models.ScheduledJob:
    """Create a scheduled job."""
    row = models.ScheduledJob(**job_data, created_by=user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_scheduled_job_run(db: Session, job_id: int, status: str, run_at: datetime) -> models.ScheduledJob | None:
    """Record a job run outcome. Returns None when the job does not exist."""
    row = db.query(models.ScheduledJob).filter(models.ScheduledJob.id == job_id).first()
    if not row:
        return None
    row.last_run_at = run_at
    row.last_status = status
    db.commit()
    db.refresh(row)
    return row


def delete_scheduled_job(db: Session, job_id: int) -> models.ScheduledJob | None:
    """Delete a scheduled job by ID. Returns the deleted row, or None if not found."""
    row = db.query(models.ScheduledJob).filter(models.ScheduledJob.id == job_id).first()
    if not row:
        return None
    db.delete(row)
    db.commit()
    return row
