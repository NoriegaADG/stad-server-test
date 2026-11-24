
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.db import SessionLocal, engine
from app.generators.synthetic_log_generator import (
    generate_synthetic_log,
)
from app.main import app
from app.models import Role, User

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

    assert response.status_code == 200

    data = response.json()

    assert data["node_name"] == "NODE0001"
    assert data["result"] == "PASS"
    assert data["duration_seconds"] == 120.0
    assert data["saved"] is False
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