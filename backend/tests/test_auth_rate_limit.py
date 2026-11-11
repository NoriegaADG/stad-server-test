
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, LoginAttempt

def test_login_rate_limit():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    email = f"blocked-{uuid4().hex}@stad.local"
    test_ip = "198.51.100.77"

    try:
        with TestClient(
            app,
            client=(test_ip, 50000),
        ) as client:

            csrf_response = client.get(
                "/api/v1/auth/csrf"
            )

            assert csrf_response.status_code == 200

            csrf_token = csrf_response.json()["csrf_token"]

            status_codes = []

            for _ in range(6):
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

                status_codes.append(response.status_code)

            assert status_codes == [
                401,
                401,
                401,
                401,
                429,
                429,
            ]

            assert "stad_access_token" not in client.cookies

        with SessionLocal() as db:

            failed_attempts = db.scalar(
                select(func.count())
                .select_from(LoginAttempt)
                .where(LoginAttempt.email == email)
            )

            assert failed_attempts == 5

            audit_events = db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "LOGIN_FAILED",
                    AuditLog.details[
                        "attempted_email"
                    ].as_string() == email,
                )
            )

            assert audit_events == 5

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
                    AuditLog.details[
                        "attempted_email"
                    ].as_string() == email,
                )
            )

            db.commit()