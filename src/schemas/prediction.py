"""Schemas for the prediction endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Feature vector for a model prediction."""

    features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Feature names mapped to values, as expected by the model.",
    )


class PredictionResponse(BaseModel):
    """Successful prediction result.

    ``prediction`` and ``probabilities`` are kept untyped because their shape
    is model-specific (the ML contract is defined by the registered model).
    """

    status: str = "ok"
    prediction: Any = None
    probabilities: Optional[List[Any]] = None
