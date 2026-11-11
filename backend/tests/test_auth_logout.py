
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, Role, User

def test_logout_clears_session_and_creates_audit():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    email = f"logout-test-{uuid4().hex}@stad.local"
    password = "STAD-Test-Logout-2026!"

    with SessionLocal() as db:
        role = db.scalar(
            select(Role).where(Role.code == "VIEWER")
        )

        assert role is not None

        user = User(
            email=email,
            full_name="STAD Logout Test",
            password_hash=hash_password(password),
            role_id=role.id,
            is_active=True,
            must_change_password=False,
            token_version=1,
        )

        db.add(user)
        db.commit()

        user_id = user.id

    try:
        with TestClient(app) as client:
            csrf = client.get(
                "/api/v1/auth/csrf"
            ).json()["csrf_token"]

            login = client.post(
                "/api/v1/auth/login",
                json={
                    "email": email,
                    "password": password,
                },
                headers={
                    "X-CSRF-Token": csrf,
                },
            )

            assert login.status_code == 200
            assert "stad_access_token" in client.cookies

            csrf = client.get(
                "/api/v1/auth/csrf"
            ).json()["csrf_token"]

            logout = client.post(
                "/api/v1/auth/logout",
                headers={
                    "X-CSRF-Token": csrf,
                },
            )

            assert logout.status_code == 200

            assert "stad_access_token" not in client.cookies

            response = client.get("/api/v1/auth/me")

            assert response.status_code == 401

        with SessionLocal() as db:
            audit = db.scalar(
                select(AuditLog).where(
                    AuditLog.user_id == user_id,
                    AuditLog.action == "LOGOUT",
                )
            )

            assert audit is not None

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.user_id == user_id
                )
            )

            user = db.get(User, user_id)

            if user is not None:
                db.delete(user)

            db.commit()