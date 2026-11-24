from uuid import uuid4

import pytest
import hashlib

from fastapi.testclient import TestClient

from sqlalchemy import delete, func, select

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.db import SessionLocal, engine
from app.generators.synthetic_log_generator import (
    generate_synthetic_log,
)
from app.main import app
from app.models import (
    AuditLog,
    Role,
    TestExecution as ExecutionRecord,
    User,
)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

UPLOAD_URL = "/api/v1/logs/upload"


@pytest.fixture
def make_token():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    created_ids = []

    def create_user_token(role_code: str):
        with SessionLocal() as db:
            role = db.scalar(
                select(Role).where(
                    Role.code == role_code
                )
            )

            assert role is not None

            user = User(
                email=f"upload-{uuid4().hex}@stad.local",
                full_name="STAD Upload Test",
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
            db.refresh(user)

            created_ids.append(user.id)

            return create_access_token(
                user_id=user.id,
                token_version=user.token_version,
            )

    yield create_user_token

    with SessionLocal() as db:
        for user_id in created_ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.user_id == user_id
                )
            )

            db.execute(
                delete(ExecutionRecord).where(
                    ExecutionRecord.uploaded_by_user_id
                    == user_id
                )
            )

            user = db.get(User, user_id)

            if user is not None:
                db.delete(user)

        db.commit()


def valid_content() -> bytes:
    return generate_synthetic_log(
        result="PASS",
        node_name="NODE0001",
    ).encode("utf-8")


def csrf_headers(client: TestClient) -> dict:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200

    return {
        "X-CSRF-Token": response.json()["csrf_token"]
    }


@pytest.mark.parametrize(
    "role_code",
    ["ADMIN", "ENGINEER"],
)
def test_upload_allowed_roles(make_token, role_code):
    token = make_token(role_code)

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    "sample.log",
                    valid_content(),
                    "text/plain",
                )
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 201

    data = response.json()

    assert data["node_name"] == "NODE0001"
    assert data["result"] == "PASS"
    assert data["duration_seconds"] == 120.0
    assert data["saved"] is True
    assert isinstance(data["id"], int)
    assert data["id"] > 0
    assert len(data["sha256"]) == 64


def test_upload_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    "sample.log",
                    valid_content(),
                )
            },
        )

    assert response.status_code == 401


def test_upload_rejects_viewer(make_token):
    token = make_token("VIEWER")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    "sample.log",
                    valid_content(),
                )
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 403


def test_upload_requires_csrf(make_token):
    token = make_token("ENGINEER")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    "sample.log",
                    valid_content(),
                )
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Invalid CSRF token"
    )


@pytest.mark.parametrize(
    "filename, content",
    [
        ("invalid.exe", b"invalid"),
        ("sample.log", b"invalid content"),
        ("sample.log", b"\xff\xfe\xff"),
    ],
)
def test_upload_rejects_invalid_files(
        make_token,
        filename,
        content,
):
    token = make_token("ENGINEER")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    filename,
                    content,
                )
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 422


def test_upload_rejects_large_file(
        make_token,
        monkeypatch,
):
    monkeypatch.setattr(
        "app.api.logs.MAX_LOG_FILE_BYTES",
        100,
    )

    token = make_token("ENGINEER")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    "large.log",
                    b"x" * 101,
                )
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 413


def test_upload_requires_file(make_token):
    token = make_token("ENGINEER")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            headers=csrf_headers(client),
        )

    assert response.status_code == 422


def test_upload_duplicate_returns_409(make_token):
    token = make_token("ENGINEER")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        headers = csrf_headers(client)

        files = {
            "file": (
                "duplicate.log",
                valid_content(),
                "text/plain",
            )
        }

        first = client.post(
            UPLOAD_URL,
            files=files,
            headers=headers,
        )

        second = client.post(
            UPLOAD_URL,
            files=files,
            headers=headers,
        )

    assert first.status_code == 201
    assert second.status_code == 409

    assert second.json()["detail"] == (
        "A log with this SHA-256 already exists"
    )


def test_upload_incomplete_execution(make_token):
    token = make_token("ENGINEER")

    content = generate_synthetic_log(
        result="INCOMPLETE",
        node_name="NODE0004",
    ).encode("utf-8")

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        response = client.post(
            UPLOAD_URL,
            files={
                "file": (
                    "NODE0004_incomplete.log",
                    content,
                    "text/plain",
                )
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 201

    data = response.json()

    assert data["result"] == "INCOMPLETE"
    assert data["finished_at"] is None
    assert data["duration_seconds"] is None
    assert data["saved"] is True


def test_concurrent_upload_same_log_saves_once(make_token):
    token = make_token("ENGINEER")

    node_name = f"NODE{uuid4().hex[:12]}"

    content = generate_synthetic_log(
        result="PASS",
        node_name=node_name,
    ).encode("utf-8")

    expected_sha256 = hashlib.sha256(
        content
    ).hexdigest()

    barrier = Barrier(2)

    def upload_once():
        with TestClient(app) as client:
            client.cookies.set(
                "stad_access_token",
                token,
            )

            headers = csrf_headers(client)

            barrier.wait(timeout=15)

            response = client.post(
                UPLOAD_URL,
                files={
                    "file": (
                        "concurrent.log",
                        content,
                        "text/plain",
                    )
                },
                headers=headers,
            )

            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(upload_once)
        second = executor.submit(upload_once)

        results = [
            first.result(timeout=30),
            second.result(timeout=30),
        ]

    statuses = sorted(
        status for status, _ in results
    )

    assert statuses == [201, 409]

    created = next(
        body
        for status, body in results
        if status == 201
    )

    conflict = next(
        body
        for status, body in results
        if status == 409
    )

    assert created["saved"] is True
    assert created["sha256"] == expected_sha256
    assert conflict["detail"] == (
        "A log with this SHA-256 already exists"
    )

    with SessionLocal() as db:
        execution_count = db.scalar(
            select(func.count())
            .select_from(ExecutionRecord)
            .where(
                ExecutionRecord.sha256 == expected_sha256
            )
        )

        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "LOG_UPLOADED",
                AuditLog.entity_type == "test_execution",
                AuditLog.entity_id == str(created["id"]),
            )
        )

    assert execution_count == 1
    assert audit_count == 1