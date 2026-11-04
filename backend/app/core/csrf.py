
import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, Request, Response

from app.core.security import get_jwt_secret

CSRF_COOKIE_NAME = "stad_csrf"

def _signature(session_id: str, nonce: str) -> str:
    message = (
        f"{len(session_id)}:{session_id}"
        f"{len(nonce)}:{nonce}"
    ).encode("utf-8")

    return hmac.new(
        get_jwt_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

def issue_csrf_token(
    response: Response,
    session_id: str,
) -> str:
    nonce = secrets.token_urlsafe(24)
    token = f"{nonce}.{_signature(session_id, nonce)}"

    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
        max_age=12 * 60 * 60,
    )

    return token

def require_csrf(
    request: Request,
    session_id: str,
) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get("X-CSRF-Token")

    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(
            cookie_token, header_token
        )
    ):
        raise HTTPException(403, "Invalid CSRF token")

    parts = cookie_token.split(".")

    if len(parts) != 2:
        raise HTTPException(403, "Invalid CSRF token")

    nonce, provided_signature = parts
    expected_signature = _signature(session_id, nonce)

    if not secrets.compare_digest(
        provided_signature, expected_signature
    ):
        raise HTTPException(403, "Invalid CSRF token")
