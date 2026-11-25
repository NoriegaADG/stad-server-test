
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


USERS_URL = "/api/v1/users"

OLD_PASSWORD = "Old-Reactivation-Test-2026!"
NEW_PASSWORD = "New-Reactivation-Test-2026!"


@pytest.fixture
def reactivate_context():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    batch = uuid4().hex
    users = {}

    definitions = [
        ("ADMIN", "ADMIN", True),
        ("ENGINEER", "ENGINEER", True),
        ("VIEWER", "VIEWER", True),
        ("TARGET_ENGINEER", "ENGINEER", False),
        ("TARGET_VIEWER", "VIEWER", False),
    ]

    with SessionLocal() as db:
        for key, role_code, active in definitions:
            role = db.scalar(
                select(Role).where(
                    Role.code == role_code
                )
            )

            assert role is not None

            user = User(
                email=(
                    f"reactivate-{key.lower()}-"
                    f"{batch}@stad.local"
                ),
                full_name=f"STAD Reactivate {key}",
                password_hash=hash_password(
                    OLD_PASSWORD
                ),
                role_id=role.id,
                is_active=active,
                must_change_password=False,
                token_version=1,
            )

            db.add(user)
            db.flush()

            users[key] = {
                "id": user.id,
                "email": user.email,
                "role": role_code,
                "token": create_access_token(
                    user_id=user.id,
                    token_version=user.token_version,
                ),
            }

        db.commit()

    yield users

    ids = [item["id"] for item in users.values()]
    text_ids = [str(value) for value in ids]

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
            delete(User).where(
                User.id.in_(ids)
            )
        )

        db.commit()


def reactivate_request(
    context,
    target_id,
    actor_role="ADMIN",
    password=NEW_PASSWORD,
    reason="REHIRE",
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
            f"{USERS_URL}/{target_id}/reactivate",
            json={
                "temporary_password": password,
                "reason": reason,
            },
            headers=headers,
        )


def test_reactivate_requires_authentication(
    reactivate_context,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["TARGET_VIEWER"]["id"],
        actor_role=None,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "actor_role",
    ["ENGINEER", "VIEWER"],
)
def test_only_admin_can_reactivate(
    reactivate_context,
    actor_role,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["TARGET_VIEWER"]["id"],
        actor_role=actor_role,
    )

    assert response.status_code == 403


def test_reactivate_requires_csrf(
    reactivate_context,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["TARGET_VIEWER"]["id"],
        include_csrf=False,
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Invalid CSRF token"
    )


@pytest.mark.parametrize(
    "target_key",
    ["TARGET_ENGINEER", "TARGET_VIEWER"],
)
def test_admin_reactivates_user_securely(
    reactivate_context,
    target_key,
):
    target = reactivate_context[target_key]
    admin = reactivate_context["ADMIN"]

    response = reactivate_request(
        reactivate_context,
        target["id"],
        reason="REHIRE",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == target["id"]
    assert data["role"] == target["role"]
    assert data["is_active"] is True
    assert data["must_change_password"] is True

    assert "password_hash" not in data
    assert "temporary_password" not in data

    with SessionLocal() as db:
        user = db.get(User, target["id"])

        assert user is not None

        assert user.is_active is True
        assert user.must_change_password is True
        assert user.token_version == 2

        assert user.password_hash != NEW_PASSWORD

        assert verify_password(
            NEW_PASSWORD,
            user.password_hash,
        )

        assert not verify_password(
            OLD_PASSWORD,
            user.password_hash,
        )

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "USER_REACTIVATED",
                AuditLog.user_id == admin["id"],
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(target["id"]),
            )
        )

        assert audit is not None
        assert audit.details["reason"] == "REHIRE"
        assert audit.details["role"] == target["role"]

        assert "temporary_password" not in audit.details

    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            target["token"],
        )

        response = client.get("/api/v1/auth/me")

    assert response.status_code == 401

    with TestClient(app) as client:
        csrf = client.get(
            "/api/v1/auth/csrf"
        ).json()["csrf_token"]

        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": target["email"],
                "password": NEW_PASSWORD,
            },
            headers={"X-CSRF-Token": csrf},
        )

        assert login.status_code == 200

        assert (
            login.json()["must_change_password"]
            is True
        )

        dashboard = client.get(
            "/api/v1/dashboard/summary"
        )

        assert dashboard.status_code == 403
        assert dashboard.json()["detail"] == (
            "Password change required"
        )


def test_cannot_reactivate_active_user(
    reactivate_context,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["ENGINEER"]["id"],
    )

    assert response.status_code == 409


def test_cannot_reactivate_admin(
    reactivate_context,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["ADMIN"]["id"],
    )

    assert response.status_code == 403


def test_nonexistent_user_returns_404(
    reactivate_context,
):
    nonexistent_id = (
        max(
            item["id"]
            for item in reactivate_context.values()
        )
        + 1_000_000
    )

    response = reactivate_request(
        reactivate_context,
        nonexistent_id,
    )

    assert response.status_code == 404


def test_invalid_user_id_returns_422(
    reactivate_context,
):
    response = reactivate_request(
        reactivate_context,
        0,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "reason",
    ["INVALID_REASON", ""],
)
def test_invalid_reason_returns_422(
    reactivate_context,
    reason,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["TARGET_VIEWER"]["id"],
        reason=reason,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "password",
    ["short", "x" * 1025],
)
def test_invalid_password_returns_422(
    reactivate_context,
    password,
):
    response = reactivate_request(
        reactivate_context,
        reactivate_context["TARGET_VIEWER"]["id"],
        password=password,
    )

    assert response.status_code == 422


def test_cannot_reuse_previous_password(
    reactivate_context,
):
    target_id = reactivate_context["TARGET_VIEWER"]["id"]

    response = reactivate_request(
        reactivate_context,
        target_id,
        password=OLD_PASSWORD,
    )

    assert response.status_code == 400

    with SessionLocal() as db:
        user = db.get(User, target_id)

        assert user is not None
        assert user.is_active is False
        assert user.token_version == 1
        assert user.must_change_password is False