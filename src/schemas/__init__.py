"""Pydantic schemas for the KRYVARACODE API.

One module per domain; aggregate imports here for convenience::

    from src.schemas import UserCreate, DatasetRead, Token
"""

from src.schemas.common import (
    ErrorDetail,
    Message,
    Paginated,
    PaginationParams,
)
from src.schemas.dataset import DatasetCreate, DatasetRead, DatasetUpdate
from src.schemas.experiment import (
    ExperimentCreate,
    ExperimentRead,
    ExperimentUpdate,
)
from src.schemas.item import ItemCreate, ItemRead
from src.schemas.model import ModelCreate, ModelRead
from src.schemas.prediction import PredictionRequest, PredictionResponse, TrainRequest
from src.schemas.process import ProcessRequest, ProcessResponse
from src.schemas.token import Token, TokenPayload
from src.schemas.user import UserBase, UserCreate, UserRead, UserUpdate

__all__ = [
    "DatasetCreate",
    "DatasetRead",
    "DatasetUpdate",
    "ErrorDetail",
    "ExperimentCreate",
    "ExperimentRead",
    "ExperimentUpdate",
    "ItemCreate",
    "ItemRead",
    "Message",
    "ModelCreate",
    "ModelRead",
    "Paginated",
    "PaginationParams",
    "PredictionRequest",
    "PredictionResponse",
    "TrainRequest",
    "ProcessRequest",
    "ProcessResponse",
    "Token",
    "TokenPayload",
    "UserBase",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
