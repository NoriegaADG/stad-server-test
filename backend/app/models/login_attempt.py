
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    __table_args__ = (
        Index(
            "ix_login_attempts_email_time",
            "email",
            "attempted_at",
        ),
        Index(
            "ix_login_attempts_ip_time",
            "ip_address",
            "attempted_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
