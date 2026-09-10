"""Schemas for the prediction endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    """Feature vector for a model prediction."""

    model_config = ConfigDict(extra="forbid")

    features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Feature names mapped to values, as expected by the model.",
        min_length=1,
    )


class PredictionResponse(BaseModel):
    """Successful prediction result.

    ``prediction`` and ``probabilities`` are kept untyped because their shape
    is model-specific (the ML contract is defined by the registered model).
    """

    status: str = "ok"
    prediction: Any = None
    probabilities: Optional[List[Any]] = None


class TrainRequest(BaseModel):
    """Arguments for model training.

    Triggers an asynchronous training run using a registered dataset.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: int = Field(..., ge=1, description="Dataset primary key to train on")
    target: str = Field(..., description="Target column name for training")
    experiment: str = Field(default="default", description="MLflow experiment name")
