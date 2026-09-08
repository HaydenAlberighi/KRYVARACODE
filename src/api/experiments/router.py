"""
Experiment management routes for KRYVARACODE AI System Stack.

Served under ``/experiments``; the version prefix is attached by ``src.api.main``.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_active_user, get_db
from src.core.exceptions import NotFoundError
from src.db import crud, models
from src.schemas import ExperimentCreate, ExperimentRead, ExperimentUpdate, Message

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("", response_model=ExperimentRead, status_code=201)
def create_experiment(
    experiment: ExperimentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Experiment:
    """Register a new experiment."""
    return crud.create_experiment(
        db, experiment_data=experiment.model_dump(), user_id=current_user.id
    )


@router.get("", response_model=List[ExperimentRead])
def list_experiments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> List[models.Experiment]:
    """List experiments."""
    return crud.get_experiments(db, skip=skip, limit=limit)


@router.get("/{experiment_id}", response_model=ExperimentRead)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Experiment:
    """Get a specific experiment by ID."""
    db_experiment = crud.get_experiment(db, experiment_id=experiment_id)
    if db_experiment is None:
        raise NotFoundError("Experiment not found")
    return db_experiment


@router.patch("/{experiment_id}", response_model=ExperimentRead)
def update_experiment(
    experiment_id: int,
    experiment: ExperimentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Experiment:
    """Partially update an experiment (status, metrics, parameters, ...)."""
    db_experiment = crud.update_experiment(
        db,
        experiment_id=experiment_id,
        experiment_data=experiment.model_dump(exclude_unset=True),
    )
    if db_experiment is None:
        raise NotFoundError("Experiment not found")
    return db_experiment


@router.delete("/{experiment_id}", response_model=Message)
def delete_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> Message:
    """Delete an experiment by ID."""
    if not crud.delete_experiment(db, experiment_id=experiment_id):
        raise NotFoundError("Experiment not found")
    return Message(detail="Experiment deleted")
