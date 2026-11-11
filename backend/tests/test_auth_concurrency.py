
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, LoginAttempt


def test_concurrent_login_attempts():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    email = f"concurrent-{uuid4().hex}@stad.local"
    test_ip = "198.51.100.78"

    number_of_requests = 6
    barrier = Barrier(number_of_requests, timeout=20)

    def attempt_login():
        with TestClient(
            app,
            client=(test_ip, 50000),
        ) as client:

            csrf_response = client.get(
                "/api/v1/auth/csrf"
            )

            assert csrf_response.status_code == 200

            csrf_token = csrf_response.json()["csrf_token"]

            barrier.wait()

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

            return response.status_code

    try:
        with ThreadPoolExecutor(
            max_workers=number_of_requests
        ) as executor:

            results = list(
                executor.map(
                    lambda _: attempt_login(),
                    range(number_of_requests),
                )
            )

        assert results.count(401) == 4, results
        assert results.count(429) == 2, results

        with SessionLocal() as db:

            attempts = db.scalar(
                select(func.count())
                .select_from(LoginAttempt)
                .where(LoginAttempt.email == email)
            )

            assert attempts == 5

            audits = db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "LOGIN_FAILED",
                    AuditLog.details[
                        "attempted_email"
                    ].as_string() == email,
                )
            )

            assert audits == 5

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