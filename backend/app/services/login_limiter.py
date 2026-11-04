
import hashlib

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import LoginAttempt

MAX_FAILED_ATTEMPTS = 5
WINDOW_MINUTES = 15

def _lock_key(category: str, value: str) -> int:
    raw = f"stad:login:{category}:{value}".encode("utf-8")

    digest = hashlib.sha256(raw).digest()

    return int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=True,
    )

def count_recent_failures(
    db: Session,
    email: str,
    ip_address: str,
) -> tuple[int, int]:

    keys = sorted({
        _lock_key("email", email),
        _lock_key("ip", ip_address),
    })

    for key in keys:
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": key},
        )

    since = datetime.now(timezone.utc) - timedelta(
        minutes=WINDOW_MINUTES
    )

    by_email = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.email == email,
            LoginAttempt.attempted_at >= since,
        )
    ) or 0

    by_ip = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.attempted_at >= since,
        )
    ) or 0

    return by_email, by_ip

def record_failed_login(
    db: Session,
    email: str,
    ip_address: str,
) -> None:
    db.add(
        LoginAttempt(
            email=email,
            ip_address=ip_address,
            attempted_at=datetime.now(timezone.utc),
        )
    )

    db.commit()