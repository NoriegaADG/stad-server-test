
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db import get_db
from app.models import AuditLog

router = APIRouter(
    tags=["Audit"],
    dependencies=[Depends(require_roles("ADMIN"))],
)

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime

class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int

@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    action: str | None = Query(default=None, max_length=50),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    filters = []

    if action is not None:
        filters.append(AuditLog.action == action)

    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)

    total = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(*filters)
    ) or 0

    records = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AuditLogPage(
        items=[
            AuditLogResponse.model_validate(record)
            for record in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )