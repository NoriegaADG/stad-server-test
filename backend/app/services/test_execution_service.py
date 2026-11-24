
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TestExecution
from app.services.audit_service import record_audit_event
from app.services.log_upload_validator import ValidatedLog

class DuplicateExecutionError(Exception):
    """The uploaded file already exists in STAD."""

def save_test_execution(
    db: Session,
    validated_log: ValidatedLog,
    uploaded_by_user_id: int,
    ip_address: str | None = None,
) -> TestExecution:

    summary = validated_log.summary

    duration_seconds = (
        int(summary.duration.total_seconds())
        if summary.duration is not None
        else None
    )

    execution = TestExecution(
        node_name=summary.node_name,
        filename=validated_log.filename,
        sha256=validated_log.sha256,
        file_size_bytes=validated_log.size_bytes,
        result=summary.result,
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        duration_seconds=duration_seconds,
        uploaded_by_user_id=uploaded_by_user_id,
    )

    try:
        db.add(execution)

        db.flush()

        record_audit_event(
            db,
            action="LOG_UPLOADED",
            user_id=uploaded_by_user_id,
            ip_address=ip_address,
            entity_type="test_execution",
            entity_id=str(execution.id),
            details={
                "filename": validated_log.filename,
                "sha256": validated_log.sha256,
                "node_name": summary.node_name,
                "result": summary.result,
            },
        )

        db.commit()

    except IntegrityError as exc:
        db.rollback()

        constraint_name = getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )

        if constraint_name == "uq_test_executions_sha256":
            raise DuplicateExecutionError(
                "A log with this SHA-256 already exists"
            ) from exc

        raise

    except Exception:
        db.rollback()
        raise

    return execution