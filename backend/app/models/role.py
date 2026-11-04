
from __future__ import annotations

from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    users: Mapped[list[User]] = relationship(
        back_populates="role",
    )
