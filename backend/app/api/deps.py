
from fastapi import Depends, HTTPException, Request
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import decode_access_token
from app.db import get_db
from app.models import User

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:

    token = request.cookies.get("stad_access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    try:
        payload = decode_access_token(token)

        subject = payload.get("sub")
        version = payload.get("tv")

        if (
            not isinstance(subject, str)
            or not subject.isdecimal()
            or type(version) is not int
        ):
            raise ValueError("Invalid token claims")

        user_id = int(subject)

    except (InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        )

    user = db.scalar(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )

    if (
        user is None
        or not user.is_active
        or user.token_version != version
    ):
        raise HTTPException(
            status_code=401,
            detail="Session is no longer valid",
        )

    return user