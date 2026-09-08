"""
CRUD operations for KRYVARACODE AI System Stack.

All functions take an explicit ``Session`` so they stay testable with any
DB engine. HTTP-specific concerns (auth, pagination parsing) live in the
routers, not here.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.security import get_password_hash, verify_password
from src.db import models


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """Get a user by ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get a user by email."""
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Get a user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    """Get multiple users."""
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(
    db: Session,
    email: str,
    username: str,
    password: str,
    full_name: Optional[str] = None,
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


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user by ID. Returns True if a row was removed."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def authenticate_user(
    db: Session, username: str, password: str
) -> Optional[models.User]:
    """Authenticate a user by username + password.

    Returns the user on success, ``None`` when credentials are invalid.
    """
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[models.Item]:
    """Get multiple items."""
    return db.query(models.Item).offset(skip).limit(limit).all()


def get_item(db: Session, item_id: int) -> Optional[models.Item]:
    """Get an item by ID."""
    return db.query(models.Item).filter(models.Item.id == item_id).first()


def create_user_item(db: Session, item: dict, user_id: int) -> models.Item:
    """Create an item for a user."""
    db_item = models.Item(**item, owner_id=user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, item_id: int) -> bool:
    """Delete an item by ID. Returns True if a row was removed."""
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------
def get_model_metadata(db: Session, model_id: int) -> Optional[models.ModelMetadata]:
    """Get model metadata by ID."""
    return (
        db.query(models.ModelMetadata)
        .filter(models.ModelMetadata.id == model_id)
        .first()
    )


def get_model_metadata_by_name(
    db: Session, name: str, version: Optional[str] = None
) -> Optional[models.ModelMetadata]:
    """Get model metadata by name and optionally version."""
    query = db.query(models.ModelMetadata).filter(models.ModelMetadata.name == name)
    if version:
        query = query.filter(models.ModelMetadata.version == version)
    return query.first()


def get_model_metadata_list(
    db: Session, skip: int = 0, limit: int = 100
) -> List[models.ModelMetadata]:
    """Get multiple model metadata entries."""
    return db.query(models.ModelMetadata).offset(skip).limit(limit).all()


def create_model_metadata(
    db: Session, model_data: dict, user_id: int
) -> models.ModelMetadata:
    """Create model metadata."""
    db_model = models.ModelMetadata(**model_data, created_by=user_id)
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


def delete_model_metadata(db: Session, model_id: int) -> bool:
    """Delete model metadata by ID. Returns True if a row was removed."""
    model = (
        db.query(models.ModelMetadata)
        .filter(models.ModelMetadata.id == model_id)
        .first()
    )
    if not model:
        return False
    db.delete(model)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------
def get_experiment(db: Session, experiment_id: int) -> Optional[models.Experiment]:
    """Get an experiment by ID."""
    return (
        db.query(models.Experiment)
        .filter(models.Experiment.id == experiment_id)
        .first()
    )


def get_experiments(
    db: Session, skip: int = 0, limit: int = 100
) -> List[models.Experiment]:
    """Get multiple experiments."""
    return db.query(models.Experiment).offset(skip).limit(limit).all()


def create_experiment(
    db: Session, experiment_data: dict, user_id: int
) -> models.Experiment:
    """Create an experiment."""
    db_experiment = models.Experiment(**experiment_data, created_by=user_id)
    db.add(db_experiment)
    db.commit()
    db.refresh(db_experiment)
    return db_experiment


def update_experiment(
    db: Session, experiment_id: int, experiment_data: dict
) -> Optional[models.Experiment]:
    """Partially update an experiment. ``None`` values are skipped.

    Returns ``None`` when the experiment does not exist.
    """
    db_experiment = (
        db.query(models.Experiment)
        .filter(models.Experiment.id == experiment_id)
        .first()
    )
    if not db_experiment:
        return None
    for field, value in experiment_data.items():
        if value is not None:
            setattr(db_experiment, field, value)
    db.commit()
    db.refresh(db_experiment)
    return db_experiment


def delete_experiment(db: Session, experiment_id: int) -> bool:
    """Delete an experiment by ID. Returns True if a row was removed."""
    experiment = (
        db.query(models.Experiment)
        .filter(models.Experiment.id == experiment_id)
        .first()
    )
    if not experiment:
        return False
    db.delete(experiment)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------
def get_dataset(db: Session, dataset_id: int) -> Optional[models.Dataset]:
    """Get a dataset by ID."""
    return db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()


def get_dataset_by_name(db: Session, name: str) -> Optional[models.Dataset]:
    """Get a dataset by name (names are unique per workspace)."""
    return db.query(models.Dataset).filter(models.Dataset.name == name).first()


def get_datasets(db: Session, skip: int = 0, limit: int = 100) -> List[models.Dataset]:
    """Get multiple datasets."""
    return db.query(models.Dataset).offset(skip).limit(limit).all()


def create_dataset(db: Session, dataset_data: dict, user_id: int) -> models.Dataset:
    """Create a dataset."""
    db_dataset = models.Dataset(**dataset_data, created_by=user_id)
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


def update_dataset(
    db: Session, dataset_id: int, dataset_data: dict
) -> Optional[models.Dataset]:
    """Partially update a dataset. ``None`` values are skipped.

    Returns ``None`` when the dataset does not exist.
    """
    db_dataset = (
        db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    )
    if not db_dataset:
        return None
    for field, value in dataset_data.items():
        if value is not None:
            setattr(db_dataset, field, value)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


def delete_dataset(db: Session, dataset_id: int) -> bool:
    """Delete a dataset by ID. Returns True if a row was removed."""
    dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not dataset:
        return False
    db.delete(dataset)
    db.commit()
    return True
