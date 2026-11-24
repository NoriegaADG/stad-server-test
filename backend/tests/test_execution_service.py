
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.db import SessionLocal, engine
from app.generators.synthetic_log_generator import (
    generate_synthetic_log,
)
from app.models import (
    AuditLog,
    Role,
    TestExecution as ExecutionRecord,
    User,
)
from app.core.security import hash_password
from app.services.log_upload_validator import (
    validate_log_file,
)
from app.services.test_execution_service import (
    DuplicateExecutionError,
    save_test_execution,
)

@pytest.fixture
def uploader_id():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    with SessionLocal() as db:
        role = db.scalar(
            select(Role).where(Role.code == "ENGINEER")
        )

        assert role is not None

        user = User(
            email=f"execution-{uuid4().hex}@stad.local",
            full_name="STAD Execution Test",
            password_hash=hash_password(
                "TestPasswordOnly-2026!"
            ),
            role_id=role.id,
            is_active=True,
            must_change_password=False,
            token_version=1,
        )

        db.add(user)
        db.commit()

        user_id = user.id

    yield user_id

    with SessionLocal() as db:
        db.execute(
            delete(AuditLog).where(
                AuditLog.user_id == user_id
            )
        )

        db.execute(
            delete(ExecutionRecord).where(
                ExecutionRecord.uploaded_by_user_id == user_id
            )
        )

        user = db.get(User, user_id)

        if user is not None:
            db.delete(user)

        db.commit()


def create_validated_log(result="PASS"):
    node_name = f"NODE{uuid4().hex[:12]}"

    content = generate_synthetic_log(
        result=result,
        node_name=node_name,
    ).encode("utf-8")

    return validate_log_file(
        filename="execution.log",
        content=content,
    )


def test_saves_execution_and_audit(uploader_id):
    validated = create_validated_log()

    with SessionLocal() as db:
        execution = save_test_execution(
            db=db,
            validated_log=validated,
            uploaded_by_user_id=uploader_id,
            ip_address="127.0.0.1",
        )

        execution_id = execution.id

    with SessionLocal() as db:
        saved = db.get(ExecutionRecord, execution_id)

        assert saved is not None
        assert saved.node_name == validated.summary.node_name
        assert saved.result == "PASS"
        assert saved.duration_seconds == 120
        assert saved.sha256 == validated.sha256
        assert saved.uploaded_by_user_id == uploader_id

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.user_id == uploader_id,
                AuditLog.action == "LOG_UPLOADED",
                AuditLog.entity_id == str(execution_id),
            )
        )

        assert audit is not None
        assert audit.details["sha256"] == validated.sha256


def test_rejects_duplicate_sha256(uploader_id):
    validated = create_validated_log()

    with SessionLocal() as db:
        save_test_execution(
            db=db,
            validated_log=validated,
            uploaded_by_user_id=uploader_id,
        )

        with pytest.raises(DuplicateExecutionError):
            save_test_execution(
                db=db,
                validated_log=validated,
                uploaded_by_user_id=uploader_id,
            )

    with SessionLocal() as db:
        execution_count = db.scalar(
            select(func.count())
            .select_from(ExecutionRecord)
            .where(
                ExecutionRecord.sha256 == validated.sha256
            )
        )

        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == uploader_id,
                AuditLog.action == "LOG_UPLOADED",
            )
        )

    assert execution_count == 1
    assert audit_count == 1


def test_rolls_back_when_audit_fails(
    uploader_id,
    monkeypatch,
):
    validated = create_validated_log()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(
        "app.services.test_execution_service.record_audit_event",
        fail_audit,
    )

    with SessionLocal() as db:
        with pytest.raises(
            RuntimeError,
            match="Audit unavailable",
        ):
            save_test_execution(
                db=db,
                validated_log=validated,
                uploaded_by_user_id=uploader_id,
            )

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count())
            .select_from(ExecutionRecord)
            .where(
                ExecutionRecord.sha256 == validated.sha256
            )
        )

    assert count == 0


def test_same_filename_different_content_allowed(uploader_id):
    first_log = create_validated_log("PASS")
    second_log = create_validated_log("FAIL")

    assert first_log.filename == second_log.filename
    assert first_log.sha256 != second_log.sha256

    with SessionLocal() as db:
        first = save_test_execution(
            db=db,
            validated_log=first_log,
            uploaded_by_user_id=uploader_id,
        )

        second = save_test_execution(
            db=db,
            validated_log=second_log,
            uploaded_by_user_id=uploader_id,
        )

        assert first.id != second.id
        assert first.sha256 != second.sha256