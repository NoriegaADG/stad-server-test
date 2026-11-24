
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import and_, delete, or_, select

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, Role, User


RESET_URL = "/api/v1/users"
OLD_PASSWORD = "Initial-Reset-Test-2026!"
NEW_PASSWORD = "Replacement-Reset-Test-2026!"

@pytest.fixture
def reset_context():
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
                email=f"reset-{code.lower()}-{batch}@stad.local",
                full_name=f"Reset Test {code}",
                password_hash=hash_password(OLD_PASSWORD),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                token_version=1,
            )

            db.add(user)
            db.flush()

            users[code] = {
                "id": user.id,
                "token": create_access_token(
                    user_id=user.id,
                    token_version=user.token_version,
                ),
            }

        db.commit()

    yield users

    ids = [data["id"] for data in users.values()]
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


def reset_request(
    context,
    target_id,
    actor_role="ADMIN",
    password=NEW_PASSWORD,
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

        return client.post(
            f"{RESET_URL}/{target_id}/reset-password",
            json={"temporary_password": password},
            headers=headers,
        )


def test_reset_requires_authentication(reset_context):
    response = reset_request(
        reset_context,
        reset_context["VIEWER"]["id"],
        actor_role=None,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["ENGINEER", "VIEWER"],
)
def test_only_admin_can_reset(reset_context, role):
    response = reset_request(
        reset_context,
        reset_context["VIEWER"]["id"],
        actor_role=role,
    )

    assert response.status_code == 403


def test_reset_requires_csrf(reset_context):
    response = reset_request(
        reset_context,
        reset_context["VIEWER"]["id"],
        include_csrf=False,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Invalid CSRF token"
    )


@pytest.mark.parametrize(
    "role",
    ["ENGINEER", "VIEWER"],
)
def test_admin_resets_password_securely(
    reset_context,
    role,
):
    target_id = reset_context[role]["id"]
    old_token = reset_context[role]["token"]

    response = reset_request(
        reset_context,
        target_id,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == target_id
    assert data["role"] == role
    assert data["must_change_password"] is True
    assert "password_hash" not in data
    assert "temporary_password" not in data

    with SessionLocal() as db:
        user = db.get(User, target_id)
        assert user is not None

        assert user.password_hash != NEW_PASSWORD

        assert verify_password(
            NEW_PASSWORD,
            user.password_hash,
        )

        assert user.token_version == 2
        assert user.must_change_password is True

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "USER_PASSWORD_RESET",
                AuditLog.user_id == (
                    reset_context["ADMIN"]["id"]
                ),
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(target_id),
            )
        )

        assert audit is not None
        assert audit.details["role"] == role
        assert "temporary_password" not in audit.details

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            old_token,
        )

        previous_session = client.get(
            "/api/v1/auth/me"
        )

    assert previous_session.status_code == 401


def test_admin_cannot_reset_admin(reset_context):
    response = reset_request(
        reset_context,
        reset_context["ADMIN"]["id"],
    )

    assert response.status_code == 403


def test_reset_nonexistent_user_returns_404(
    reset_context,
):
    nonexistent_id = (
        max(data["id"] for data in reset_context.values())
        + 1_000_000
    )

    response = reset_request(
        reset_context,
        nonexistent_id,
    )

    assert response.status_code == 404


def test_reset_invalid_id_returns_422(reset_context):
    response = reset_request(
        reset_context,
        0,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "password",
    ["short", "x" * 1025],
)
def test_reset_rejects_invalid_password(
    reset_context,
    password,
):
    response = reset_request(
        reset_context,
        reset_context["VIEWER"]["id"],
        password=password,
    )

    assert response.status_code == 422