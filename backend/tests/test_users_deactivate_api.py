
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import and_, delete, or_, select

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, Role, User


USERS_URL = "/api/v1/users"
TEST_PASSWORD = "STAD-Deactivation-Test-2026!"


@pytest.fixture
def deactivate_context():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    batch = uuid4().hex
    users = {}

    with SessionLocal() as db:
        for code in ("ADMIN", "ENGINEER", "VIEWER"):
            role = db.scalar(
                select(Role).where(Role.code == code)
            )

            assert role is not None

            user = User(
                email=f"deactivate-{code.lower()}-{batch}@stad.local",
                full_name=f"Deactivate Test {code}",
                password_hash=hash_password(TEST_PASSWORD),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                token_version=1,
            )

            db.add(user)
            db.flush()

            users[code] = {
                "id": user.id,
                "email": user.email,
                "token": create_access_token(
                    user_id=user.id,
                    token_version=user.token_version,
                ),
            }

        db.commit()

    yield users

    ids = [user["id"] for user in users.values()]
    text_ids = [str(user_id) for user_id in ids]

    with SessionLocal() as db:
        db.execute(
            delete(AuditLog).where(
                or_(
                    AuditLog.user_id.in_(ids),
                    and_(
                        AuditLog.entity_type == "user",
                        AuditLog.entity_id.in_(text_ids),
                    ),
                )
            )
        )

        db.execute(
            delete(User).where(User.id.in_(ids))
        )

        db.commit()


def deactivate_request(
    context,
    target_id,
    actor_role="ADMIN",
    reason="EMPLOYMENT_ENDED",
    include_csrf=True,
):
    with TestClient(app) as client:
        if actor_role is not None:
            client.cookies.set(
                "stad_access_token",
                context[actor_role]["token"],
            )

        headers = {}

        if include_csrf:
            csrf_response = client.get(
                "/api/v1/auth/csrf"
            )

            assert csrf_response.status_code == 200

            headers["X-CSRF-Token"] = (
                csrf_response.json()["csrf_token"]
            )

        return client.patch(
            f"{USERS_URL}/{target_id}/deactivate",
            json={"reason": reason},
            headers=headers,
        )


def test_deactivate_requires_authentication(
    deactivate_context,
):
    response = deactivate_request(
        deactivate_context,
        deactivate_context["VIEWER"]["id"],
        actor_role=None,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["ENGINEER", "VIEWER"],
)
def test_only_admin_can_deactivate(
    deactivate_context,
    role,
):
    response = deactivate_request(
        deactivate_context,
        deactivate_context["VIEWER"]["id"],
        actor_role=role,
    )

    assert response.status_code == 403


def test_deactivate_requires_csrf(
    deactivate_context,
):
    response = deactivate_request(
        deactivate_context,
        deactivate_context["VIEWER"]["id"],
        include_csrf=False,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Invalid CSRF token"
    )


def test_admin_deactivates_user_securely(
    deactivate_context,
):
    target = deactivate_context["ENGINEER"]
    admin = deactivate_context["ADMIN"]

    response = deactivate_request(
        deactivate_context,
        target["id"],
        reason="EMPLOYMENT_ENDED",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == target["id"]
    assert data["role"] == "ENGINEER"
    assert data["is_active"] is False

    with SessionLocal() as db:
        user = db.get(User, target["id"])

        assert user is not None
        assert user.is_active is False
        assert user.token_version == 2

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "USER_DEACTIVATED",
                AuditLog.user_id == admin["id"],
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(target["id"]),
            )
        )

        assert audit is not None
        assert audit.details["reason"] == (
            "EMPLOYMENT_ENDED"
        )

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            target["token"],
        )

        previous_session = client.get(
            "/api/v1/auth/me"
        )

    assert previous_session.status_code == 401

    with TestClient(app) as client:
        csrf = client.get(
            "/api/v1/auth/csrf"
        ).json()["csrf_token"]

        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": target["email"],
                "password": TEST_PASSWORD,
            },
            headers={
                "X-CSRF-Token": csrf,
            },
        )

    assert login.status_code == 401


def test_cannot_deactivate_twice(
    deactivate_context,
):
    target_id = deactivate_context["VIEWER"]["id"]

    first = deactivate_request(
        deactivate_context,
        target_id,
    )

    second = deactivate_request(
        deactivate_context,
        target_id,
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_cannot_deactivate_admin(
    deactivate_context,
):
    response = deactivate_request(
        deactivate_context,
        deactivate_context["ADMIN"]["id"],
    )

    assert response.status_code == 403


def test_nonexistent_user_returns_404(
    deactivate_context,
):
    nonexistent_id = (
        max(
            user["id"]
            for user in deactivate_context.values()
        )
        + 1_000_000
    )

    response = deactivate_request(
        deactivate_context,
        nonexistent_id,
    )

    assert response.status_code == 404


def test_invalid_id_returns_422(
    deactivate_context,
):
    response = deactivate_request(
        deactivate_context,
        0,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "reason",
    ["INVALID_REASON", ""],
)
def test_invalid_reason_returns_422(
    deactivate_context,
    reason,
):
    response = deactivate_request(
        deactivate_context,
        deactivate_context["VIEWER"]["id"],
        reason=reason,
    )

    assert response.status_code == 422