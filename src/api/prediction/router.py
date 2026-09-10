"""
Prediction endpoints for KRYVARACODE AI System Stack.

Served under ``/predict``; the version prefix is attached by ``src.api.main``.
"""

from __future__ import annotations

from typing import Any, Union

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_active_user, get_db
from src.api.prediction.lifecycle_service import lifecycle_service
from src.api.prediction.monitoring_service import monitoring_service
from src.api.prediction.service import prediction_service
from src.db import models
from src.schemas import PredictionRequest, PredictionResponse, TrainRequest
from src.tasks.prediction import predict_task, train_task

router = APIRouter(prefix="/predict", tags=["prediction"])


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def predict(
    request: PredictionRequest,
    current_user: models.User = Depends(get_current_active_user),
) -> dict[str, Any]:
    task = predict_task.delay(request.features)
    return {"task_id": task.id, "status": "pending"}


@router.get("/{task_id}", response_model=Union[PredictionResponse, dict[str, Any]])
def get_prediction_status(
    task_id: str,
    current_user: models.User = Depends(get_current_active_user),
) -> PredictionResponse | dict[str, Any]:
    res = AsyncResult(task_id)
    if res.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    elif res.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(res.info)}
    elif res.state == "SUCCESS":
        result = res.result
        return PredictionResponse(
            prediction=result.get("prediction"),
            probabilities=result.get("probabilities"),
        )
    return {"task_id": task_id, "status": res.state}


@router.get("/model-info", response_model=dict[str, Any])
def get_model_info(
    current_user: models.User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Get information about the currently loaded model."""
    return prediction_service.get_model_info()


@router.post("/reload-model", response_model=dict[str, Any])
def reload_model(
    current_user: models.User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Force a reload of the model from MLflow (after model promotion)."""
    return prediction_service.reload_model()


@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def train(
    request: TrainRequest,
    current_user: models.User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Trigger a training run asynchronously."""
    task = train_task.delay(
        dataset_id=request.dataset_id,
        target=request.target,
        experiment=request.experiment,
        user_id=current_user.id,
    )
    return {"task_id": task.id, "status": "training_started"}


@router.post("/promote", status_code=status.HTTP_202_ACCEPTED)
def promote_model(
    version: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Promote a model version to Production (if metrics superior to current prod)."""
    success, message = lifecycle_service.promote_model(db, version)
    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=message)
    return {"status": "promoted", "message": message}


@router.get("/drift")
def check_drift(
    feature_names: list[str],
    reference_data: dict[str, list[float]],
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Check for feature drift in recent predictions vs reference data."""
    is_drifted, drift_report = monitoring_service.check_for_drift(
        db, feature_names, reference_data
    )
    return {"is_drifted": is_drifted, "drift_report": drift_report}
