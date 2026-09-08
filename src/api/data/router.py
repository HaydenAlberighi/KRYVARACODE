"""
Data management routes for KRYVARACODE AI System Stack.

Served under ``/data``; the version prefix is attached by ``src.api.main``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from src.api.deps import get_current_active_user, get_db
from src.core.config import settings
from src.core.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from src.db import crud, models
from src.schemas import (
    DatasetCreate,
    DatasetRead,
    DatasetUpdate,
    Message,
    ProcessRequest,
    ProcessResponse,
)
from src.utils.helpers import ensure_dir

router = APIRouter(prefix="/data", tags=["data"])

_FORMAT_BY_SUFFIX = {
    ".csv": "csv",
    ".parquet": "parquet",
    ".json": "json",
}


@router.post("/process", response_model=ProcessResponse, summary="Process data (stub)")
def process_data(
    request: ProcessRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> ProcessResponse:
    """Submit data to the processing pipeline.

    Stub: the real validation/transformation/storage pipeline is not wired
    yet. Returns an acknowledgment so consumers can build against the
    contract.
    """
    return ProcessResponse(
        status="queued",
        processed_at=datetime.now(timezone.utc),
        processed_by=current_user.username,
        message=(
            f"Received {len(request.payload)} payload entries; "
            "pipeline is not implemented yet."
        ),
    )


@router.post("/datasets", response_model=DatasetRead, status_code=201)
def create_dataset(
    dataset: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Dataset:
    """Register a new dataset."""
    if crud.get_dataset_by_name(db, name=dataset.name) is not None:
        raise ConflictError(f"Dataset '{dataset.name}' already exists")
    return crud.create_dataset(
        db, dataset_data=dataset.model_dump(), user_id=current_user.id
    )


@router.post("/datasets/upload", response_model=DatasetRead, status_code=201)
def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Dataset:
    """Upload a data file and register it as a dataset."""
    suffix = Path(file.filename or "").suffix.lower()
    file_format = _FORMAT_BY_SUFFIX.get(suffix)
    if file_format is None:
        raise ValidationFailedError(
            f"Unsupported file format '{suffix or 'unknown'}'; expected .csv, .parquet or .json"
        )
    stem = Path(file.filename or "").stem
    dataset_name = ((name or stem).strip() or "upload")[:100]
    if crud.get_dataset_by_name(db, name=dataset_name) is not None:
        raise ConflictError(f"Dataset '{dataset_name}' already exists")

    uploads_dir = Path(settings.DATA_DIR) / "uploads"
    ensure_dir(str(uploads_dir))
    stored_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').name}"
    storage_path = uploads_dir / stored_name
    storage_path.write_bytes(file.file.read())

    dataset_data = DatasetCreate(
        name=dataset_name,
        storage_uri=str(storage_path),
        format=file_format,
    ).model_dump()
    return crud.create_dataset(db, dataset_data=dataset_data, user_id=current_user.id)


@router.get("/datasets", response_model=List[DatasetRead])
def list_datasets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> List[models.Dataset]:
    """List registered datasets."""
    return crud.get_datasets(db, skip=skip, limit=limit)


@router.get("/datasets/{dataset_id}", response_model=DatasetRead)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Dataset:
    """Get a specific dataset by ID."""
    db_dataset = crud.get_dataset(db, dataset_id=dataset_id)
    if db_dataset is None:
        raise NotFoundError("Dataset not found")
    return db_dataset


@router.patch("/datasets/{dataset_id}", response_model=DatasetRead)
def update_dataset(
    dataset_id: int,
    dataset: DatasetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Dataset:
    """Partially update a dataset."""
    db_dataset = crud.update_dataset(
        db, dataset_id=dataset_id, dataset_data=dataset.model_dump(exclude_unset=True)
    )
    if db_dataset is None:
        raise NotFoundError("Dataset not found")
    return db_dataset


@router.delete("/datasets/{dataset_id}", response_model=Message)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> Message:
    """Delete a dataset by ID."""
    if not crud.delete_dataset(db, dataset_id=dataset_id):
        raise NotFoundError("Dataset not found")
    return Message(detail="Dataset deleted")
