
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

def record_audit_event(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    ip_address: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:

    audit = AuditLog(
        action=action,
        user_id=user_id,
        ip_address=ip_address,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details if details is not None else {},
    )

    db.add(audit)

    return audit
