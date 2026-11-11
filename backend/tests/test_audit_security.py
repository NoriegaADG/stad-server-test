
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db import SessionLocal, engine
from app.main import app
from app.models import Role, User

def test_audit_logs_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/audit-logs")

    assert response.status_code == 401

@pytest.fixture
def viewer_token():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    with SessionLocal() as db:
        role = db.scalar(
            select(Role).where(Role.code == "VIEWER")
        )

        assert role is not None

        viewer = User(
            email=f"viewer-{uuid4().hex}@stad.local",
            full_name="STAD Automated Viewer",
            password_hash=hash_password(
                "TestPasswordOnly-2026!"
            ),
            role_id=role.id,
            is_active=True,
            must_change_password=False,
            token_version=1,
        )

        db.add(viewer)
        db.commit()

        try:
            token = create_access_token(
                user_id=viewer.id,
                token_version=viewer.token_version,
            )

            yield token

        finally:
            db.delete(viewer)
            db.commit()

def test_audit_logs_denies_viewer(viewer_token):
    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            viewer_token,
        )

        response = client.get("/api/v1/audit-logs")

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Insufficient permissions"
    )


@pytest.fixture
def admin_token():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    with SessionLocal() as db:
        role = db.scalar(
            select(Role).where(Role.code == "ADMIN")
        )

        assert role is not None

        admin = User(
            email=f"admin-{uuid4().hex}@stad.local",
            full_name="STAD Automated Admin",
            password_hash=hash_password(
                "TestPasswordOnly-2026!"
            ),
            role_id=role.id,
            is_active=True,
            must_change_password=False,
            token_version=1,
        )

        db.add(admin)
        db.commit()

        try:
            token = create_access_token(
                user_id=admin.id,
                token_version=admin.token_version,
            )

            yield token

        finally:
            db.delete(admin)
            db.commit()

def test_audit_logs_allows_admin(admin_token):
    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            admin_token,
        )

        response = client.get(
            "/api/v1/audit-logs?page=1&page_size=5"
        )

    assert response.status_code == 200

    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert isinstance(data["items"], list)