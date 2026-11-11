
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, LoginAttempt

def test_login_invalid_credentials():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    email = f"invalid-{uuid4().hex}@stad.local"

    try:
        with TestClient(app) as client:
            csrf_response = client.get(
                "/api/v1/auth/csrf"
            )

            assert csrf_response.status_code == 200

            csrf_token = csrf_response.json()["csrf_token"]

            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": email,
                    "password": "WrongPassword123!",
                },
                headers={
                    "X-CSRF-Token": csrf_token,
                },
            )

            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid credentials"

            assert "stad_access_token" not in client.cookies

        with SessionLocal() as db:
            attempt = db.scalar(
                select(LoginAttempt).where(
                    LoginAttempt.email == email
                )
            )

            assert attempt is not None

            audit = db.scalar(
                select(AuditLog).where(
                    AuditLog.action == "LOGIN_FAILED",
                    AuditLog.details["attempted_email"].as_string()
                    == email,
                )
            )

            assert audit is not None
            assert audit.user_id is None

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(LoginAttempt).where(
                    LoginAttempt.email == email
                )
            )

            db.execute(
                delete(AuditLog).where(
                    AuditLog.action == "LOGIN_FAILED",
                    AuditLog.details["attempted_email"].as_string()
                    == email,
                )
            )

            db.commit()