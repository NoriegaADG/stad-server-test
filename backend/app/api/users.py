
import re

from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth import csrf_session_id
from app.api.deps import require_roles
from app.core.csrf import require_csrf
from app.core.security import (
    hash_password,
    verify_password,
)
from app.db import get_db
from app.models import Role, User
from app.services.audit_service import record_audit_event


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


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=150)
    role: Literal["ENGINEER", "VIEWER"]
    temporary_password: str = Field(
        min_length=12,
        max_length=1024,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()

        if not re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+",
            email,
        ):
            raise ValueError("Invalid email address")

        return email

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()

        if not name:
            raise ValueError("Full name is required")

        return name


@router.get("", response_model=UserPage)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
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

@router.post(
    "",
    response_model=UserListItem,
    status_code=201,
)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("ADMIN")),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    role = db.scalar(
        select(Role).where(
            Role.code == payload.role
        )
    )

    if role is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid user role",
        )

    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(
            payload.temporary_password
        ),
        role_id=role.id,
        is_active=True,
        must_change_password=True,
        token_version=1,
    )

    try:
        db.add(new_user)

        db.flush()

        record_audit_event(
            db,
            action="USER_CREATED",
            user_id=admin.id,
            ip_address=(
                request.client.host
                if request.client is not None
                else None
            ),
            entity_type="user",
            entity_id=str(new_user.id),
            details={
                "email": new_user.email,
                "role": role.code,
            },
        )

        db.commit()

    except IntegrityError as exc:
        db.rollback()

        constraint_name = getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )

        if constraint_name in {
            "ix_users_email",
            "users_email_key",
        }:
            raise HTTPException(
                status_code=409,
                detail="Email already registered",
            ) from exc

        raise

    except Exception:
        db.rollback()
        raise

    return UserListItem(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        role=role.code,
        is_active=new_user.is_active,
        must_change_password=(
            new_user.must_change_password
        ),
    )


class ResetPasswordRequest(BaseModel):
    temporary_password: str = Field(
        min_length=12,
        max_length=1024,
    )

@router.post(
    "/{user_id}/reset-password",
    response_model=UserListItem,
)

def reset_user_password(
    payload: ResetPasswordRequest,
    request: Request,
    user_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("ADMIN")),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    target_user = db.scalar(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
        .with_for_update(of=User)
    )

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if target_user.role.code not in {
        "ENGINEER",
        "VIEWER",
    }:
        raise HTTPException(
            status_code=403,
            detail="Cannot reset this user's password",
        )

    try:
        target_user.password_hash = hash_password(
            payload.temporary_password
        )

        target_user.must_change_password = True

        target_user.token_version += 1

        record_audit_event(
            db,
            action="USER_PASSWORD_RESET",
            user_id=admin.id,
            ip_address=(
                request.client.host
                if request.client is not None
                else None
            ),
            entity_type="user",
            entity_id=str(target_user.id),
            details={
                "email": target_user.email,
                "role": target_user.role.code,
            },
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return UserListItem(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=target_user.role.code,
        is_active=target_user.is_active,
        must_change_password=(
            target_user.must_change_password
        ),
    )

class DeactivateUserRequest(BaseModel):
    reason: Literal[
        "EMPLOYMENT_ENDED",
        "ACCESS_NO_LONGER_REQUIRED",
        "SECURITY",
        "OTHER",
    ]


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserListItem,
)
def deactivate_user(
    payload: DeactivateUserRequest,
    request: Request,
    user_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("ADMIN")),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    target_user = db.scalar(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
        .with_for_update(of=User)
    )

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if target_user.role.code == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Cannot deactivate administrators",
        )

    if not target_user.is_active:
        raise HTTPException(
            status_code=409,
            detail="User is already inactive",
        )

    try:
        target_user.is_active = False
        target_user.token_version += 1

        record_audit_event(
            db,
            action="USER_DEACTIVATED",
            user_id=admin.id,
            ip_address=(
                request.client.host
                if request.client is not None
                else None
            ),
            entity_type="user",
            entity_id=str(target_user.id),
            details={
                "email": target_user.email,
                "role": target_user.role.code,
                "reason": payload.reason,
            },
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return UserListItem(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=target_user.role.code,
        is_active=target_user.is_active,
        must_change_password=(
            target_user.must_change_password
        ),
    )


class ReactivateUserRequest(BaseModel):
    temporary_password: str = Field(
        min_length=12,
        max_length=1024,
    )

    reason: Literal[
        "REHIRE",
        "ACCESS_RESTORED",
        "OTHER",
    ]

@router.patch(
    "/{user_id}/reactivate",
    response_model=UserListItem,
)
def reactivate_user(
    payload: ReactivateUserRequest,
    request: Request,
    user_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("ADMIN")),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    target_user = db.scalar(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
        .with_for_update(of=User)
    )

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if target_user.role.code == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Cannot reactivate administrators",
        )

    if target_user.is_active:
        raise HTTPException(
            status_code=409,
            detail="User is already active",
        )

    if verify_password(
            payload.temporary_password,
            target_user.password_hash,
    ):
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Temporary password must differ from previous password",
        )

    try:
        target_user.password_hash = hash_password(
            payload.temporary_password
        )

        target_user.is_active = True

        target_user.must_change_password = True

        target_user.token_version += 1

        record_audit_event(
            db,
            action="USER_REACTIVATED",
            user_id=admin.id,
            ip_address=(
                request.client.host
                if request.client is not None
                else None
            ),
            entity_type="user",
            entity_id=str(target_user.id),
            details={
                "email": target_user.email,
                "role": target_user.role.code,
                "reason": payload.reason,
            },
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return UserListItem(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=target_user.role.code,
        is_active=target_user.is_active,
        must_change_password=(
            target_user.must_change_password
        ),
    )