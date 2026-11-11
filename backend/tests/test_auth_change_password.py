
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import hash_password, verify_password
from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, Role, User

def test_password_change_invalidates_previous_token():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    email = f"password-test-{uuid4().hex}@stad.local"
    old_password = "OldTestPassword-2026!"
    new_password = "NewTestPassword-2026!"

    with SessionLocal() as db:
        role = db.scalar(
            select(Role).where(Role.code == "VIEWER")
        )

        assert role is not None

        user = User(
            email=email,
            full_name="STAD Password Test",
            password_hash=hash_password(old_password),
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
                    "password": old_password,
                },
                headers={"X-CSRF-Token": csrf},
            )

            assert login.status_code == 200

            old_token = client.cookies.get(
                "stad_access_token"
            )

            assert old_token is not None

            csrf = client.get(
                "/api/v1/auth/csrf"
            ).json()["csrf_token"]

            response = client.post(
                "/api/v1/auth/change-password",
                json={
                    "current_password": old_password,
                    "new_password": new_password,
                },
                headers={"X-CSRF-Token": csrf},
            )

            assert response.status_code == 200
            assert "stad_access_token" not in client.cookies

            client.cookies.set(
                "stad_access_token",
                old_token,
            )

            response = client.get("/api/v1/auth/me")

            assert response.status_code == 401

        with TestClient(app) as client:
            csrf = client.get(
                "/api/v1/auth/csrf"
            ).json()["csrf_token"]

            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": email,
                    "password": new_password,
                },
                headers={"X-CSRF-Token": csrf},
            )

            assert response.status_code == 200

        with SessionLocal() as db:
            updated_user = db.get(User, user_id)

            assert updated_user is not None
            assert updated_user.token_version == 2
            assert verify_password(
                new_password,
                updated_user.password_hash,
            )

            audit = db.scalar(
                select(AuditLog).where(
                    AuditLog.user_id == user_id,
                    AuditLog.action == "PASSWORD_CHANGED",
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