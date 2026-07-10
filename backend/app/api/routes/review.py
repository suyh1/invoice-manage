from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.domain.review.service import ReviewService
from app.domain.user.models import User


router = APIRouter(prefix="/api/v1/review", tags=["review"])


@router.get("/summary")
def review_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": ReviewService().summary(db, current_user)}


@router.get("/items")
def review_items(
    queue: Literal["needs_review", "duplicates", "failed"] = Query(default="needs_review"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": ReviewService().list_items(db, current_user, queue)}
