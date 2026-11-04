
import os
import secrets

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"
TOKEN_LIFETIME_HOURS = 12
TOKEN_ISSUER = "stad-api"
TOKEN_AUDIENCE = "stad-web"

password_hasher = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return password_hasher.verify(
        password,
        password_hash,
    )

def get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "")

    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must contain at least 32 bytes"
        )

    return secret

def create_access_token(
    user_id: int,
    token_version: int,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "jti": secrets.token_urlsafe(24),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(
            hours=TOKEN_LIFETIME_HOURS
        ),
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=ALGORITHM,
    )

def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[ALGORITHM],
        issuer=TOKEN_ISSUER,
        audience=TOKEN_AUDIENCE,
        options={
            "require": [
                "sub",
                "tv",
                "jti",
                "iss",
                "aud",
                "iat",
                "nbf",
                "exp",
            ]
        },
    )
