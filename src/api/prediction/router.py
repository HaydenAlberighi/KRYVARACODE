"""
Prediction endpoints for KRYVARACODE AI System Stack.

Served under ``/predict``; the version prefix is attached by ``src.api.main``.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.api.deps import get_current_active_user
from src.api.prediction.service import prediction_service
from src.core.exceptions import ServiceUnavailableError
from src.db import models
from src.schemas import PredictionRequest, PredictionResponse

router = APIRouter(prefix="/predict", tags=["prediction"])


@router.post("/", response_model=PredictionResponse)
def predict(
    request: PredictionRequest,
    current_user: models.User = Depends(get_current_active_user),
) -> PredictionResponse:
    """Make a prediction using the loaded model."""
    try:
        result = prediction_service.predict(request.features)
    except RuntimeError as exc:
        # Model not loaded / ML deps missing — retryable once MLflow is up.
        raise ServiceUnavailableError(str(exc)) from exc
    return PredictionResponse(
        prediction=result.get("prediction"),
        probabilities=result.get("probabilities"),
    )


@router.get("/model-info", response_model=Dict[str, Any])
def get_model_info(
    current_user: models.User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Get information about the currently loaded model."""
    return prediction_service.get_model_info()


@router.post("/reload-model", response_model=Dict[str, Any])
def reload_model(
    current_user: models.User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Force a reload of the model from MLflow (after model promotion)."""
    return prediction_service.reload_model()
