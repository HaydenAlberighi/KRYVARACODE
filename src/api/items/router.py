"""
Item routes for KRYVARACODE AI System Stack.

Served under ``/items``; the version prefix is attached by ``src.api.main``.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_active_user, get_db
from src.core.exceptions import NotFoundError
from src.db import crud, models
from src.schemas import ItemCreate, ItemRead, Message

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=201)
def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Item:
    """Create an item owned by the current user."""
    return crud.create_user_item(db, item=item.model_dump(), user_id=current_user.id)


@router.get("", response_model=List[ItemRead])
def list_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> List[models.Item]:
    """List items."""
    return crud.get_items(db, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=ItemRead)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Item:
    """Get a specific item by ID."""
    db_item = crud.get_item(db, item_id=item_id)
    if db_item is None:
        raise NotFoundError("Item not found")
    return db_item


@router.delete("/{item_id}", response_model=Message)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> Message:
    """Delete an item by ID."""
    if not crud.delete_item(db, item_id=item_id):
        raise NotFoundError("Item not found")
    return Message(detail="Item deleted")
