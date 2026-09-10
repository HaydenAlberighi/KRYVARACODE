"""
Model management routes for KRYVARACODE AI System Stack.

Served under ``/models``; the version prefix is attached by ``src.api.main``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_active_user, get_db
from src.core.exceptions import NotFoundError
from src.db import crud, models
from src.schemas import Message, ModelCreate, ModelRead

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/", response_model=ModelRead, status_code=201)
def create_model_metadata(
    model: ModelCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.ModelMetadata:
    """Register metadata for a trained model artifact."""
    return crud.create_model_metadata(
        db, model_data=model.model_dump(), user_id=current_user.id
    )


@router.get("/", response_model=list[ModelRead])
def read_model_metadata(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.ModelMetadata]:
    """List registered model metadata entries."""
    return crud.get_model_metadata_list(db, skip=skip, limit=limit)


@router.get("/{model_id}", response_model=ModelRead)
def read_model_metadata_by_id(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.ModelMetadata:
    """Get a specific model by ID."""
    db_model: models.ModelMetadata | None = crud.get_model_metadata(
        db, model_id=model_id
    )
    if db_model is None:
        raise NotFoundError("Model not found")
    return db_model


@router.delete("/{model_id}", response_model=Message)
def delete_model_metadata(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> Message:
    """Delete model metadata by ID."""
    if not crud.delete_model_metadata(db, model_id=model_id):
        raise NotFoundError("Model not found")
    return Message(detail="Model deleted")


@router.get("/{model_id}/download", response_model=Message)
def download_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> Message:
    """Download a trained model artifact."""
    db_model = crud.get_model_metadata(db, model_id=model_id)
    if db_model is None:
        raise NotFoundError("Model not found")
    # In production, would serve model from MinIO/S3
    # For now, return the file path
    return Message(detail=f"Model file path: {db_model.file_path}")


@router.get("/{name}/{version}", response_model=ModelRead)
def read_model_metadata_by_name_version(
    name: str,
    version: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.ModelMetadata:
    """Get model metadata by name and version."""
    db_model = crud.get_model_metadata_by_name(db, name=name, version=version)
    if db_model is None:
        raise NotFoundError("Model not found")
    return db_model
