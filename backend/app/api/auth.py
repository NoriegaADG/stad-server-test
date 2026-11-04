
import os

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from jwt import InvalidTokenError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user

from app.core.csrf import (
    CSRF_COOKIE_NAME,
    issue_csrf_token,
    require_csrf,
)

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

from app.services.login_limiter import (
    MAX_FAILED_ATTEMPTS,
    count_recent_failures,
    record_failed_login,
)

from app.db import get_db
from app.models import User

router = APIRouter(tags=["Authentication"])

COOKIE_NAME = "stad_access_token"
SESSION_SECONDS = 12 * 60 * 60

DUMMY_PASSWORD_HASH = hash_password(
    "stad-internal-dummy-password"
)

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=1024,
    )
    new_password: str = Field(
        min_length=12,
        max_length=1024,
    )

def csrf_session_id(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)

    if token:
        try:
            payload = decode_access_token(token)
            return payload["jti"]
        except (InvalidTokenError, KeyError):
            pass

    return "preauth"

def clear_session_cookies(response: Response) -> None:
    secure_cookie = (
        os.getenv("COOKIE_SECURE", "false").lower()
        == "true"
    )

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=secure_cookie,
        httponly=True,
        samesite="lax",
    )

    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        secure=secure_cookie,
        httponly=False,
        samesite="lax",
    )

@router.get("/csrf")
def get_csrf_token(
    request: Request,
    response: Response,
):
    csrf_token = issue_csrf_token(
        response,
        csrf_session_id(request),
    )

    return {"csrf_token": csrf_token}

@router.post("/login")
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    email = credentials.email.strip().lower()

    if request.client is None:
        raise HTTPException(
            status_code=503,
            detail="Client address unavailable",
        )

    ip_address = request.client.host

    email_failures, ip_failures = count_recent_failures(
        db,
        email,
        ip_address,
    )

    if (
        email_failures >= MAX_FAILED_ATTEMPTS
        or ip_failures >= MAX_FAILED_ATTEMPTS
    ):
        db.rollback()

        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
        )

    user = db.scalar(
        select(User).where(User.email == email)
    )

    stored_hash = (
        user.password_hash
        if user is not None
        else DUMMY_PASSWORD_HASH
    )

    password_valid = verify_password(
        credentials.password,
        stored_hash,
    )

    if (
        user is None
        or not password_valid
        or not user.is_active
    ):
        record_failed_login(
            db,
            email,
            ip_address,
        )

        if (
            email_failures + 1 >= MAX_FAILED_ATTEMPTS
            or ip_failures + 1 >= MAX_FAILED_ATTEMPTS
        ):
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts",
            )

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    user_id = user.id
    token_version = user.token_version
    must_change_password = user.must_change_password

    db.rollback()

    token = create_access_token(
        user_id=user_id,
        token_version=token_version,
    )

    payload = decode_access_token(token)

    secure_cookie = (
        os.getenv("COOKIE_SECURE", "false").lower()
        == "true"
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
        max_age=SESSION_SECONDS,
    )

    issue_csrf_token(
        response,
        payload["jti"],
    )

    return {
        "message": "Login successful",
        "must_change_password": must_change_password,
    }


@router.get("/me")
def get_my_profile(
    user: User = Depends(get_current_user),
):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.code,
        "is_active": user.is_active,
        "must_change_password": (
            user.must_change_password
        ),
    }

@router.post("/change-password")
def change_password(
    credentials: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    require_csrf(
        request,
        csrf_session_id(request),
    )

    if not verify_password(
        credentials.current_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    if verify_password(
        credentials.new_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="New password must be different",
        )

    user.password_hash = hash_password(
        credentials.new_password
    )

    user.must_change_password = False

    user.token_version += 1

    db.commit()

    clear_session_cookies(response)

    return {
        "message": "Password changed successfully",
        "login_required": True,
    }

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
):

    require_csrf(
        request,
        csrf_session_id(request),
    )

    clear_session_cookies(response)

    return {
        "message": "Logout successful",
    }
