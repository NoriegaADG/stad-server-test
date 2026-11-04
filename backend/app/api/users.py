
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.db import get_db
from app.models import User

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool

class UserPage(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int

@router.get("", response_model=UserPage)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("ADMIN")),
):
    total = db.scalar(
        select(func.count()).select_from(User)
    ) or 0

    users = db.scalars(
        select(User)
        .options(selectinload(User.role))
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return UserPage(
        items=[
            UserListItem(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role.code,
                is_active=user.is_active,
                must_change_password=(
                    user.must_change_password
                ),
            )
            for user in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )