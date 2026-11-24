
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

class TestExecution(Base):
    __tablename__ = "test_executions"

    __table_args__ = (
        UniqueConstraint(
            "sha256",
            name="uq_test_executions_sha256",
        ),
        CheckConstraint(
            "result IN ('PASS', 'FAIL', 'ERROR', 'INCOMPLETE')",
            name="ck_test_executions_result",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_test_executions_file_size",
        ),
        CheckConstraint(
            "duration_seconds IS NULL "
            "OR duration_seconds >= 0",
            name="ck_test_executions_duration",
        ),
        Index(
            "ix_test_executions_node_started",
            "node_name",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    node_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    result: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    uploaded_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )