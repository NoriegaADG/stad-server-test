
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, Role, User

USERS_URL = "/api/v1/users"

@pytest.fixture

def user_context():

    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    batch = uuid4().hex
    password = "TemporaryPassword-2026!"

    with SessionLocal() as db:
        tokens = {}
        admin_id = None

        for code in ("ADMIN", "ENGINEER", "VIEWER"):
            role = db.scalar(
                select(Role).where(Role.code == code)
            )

            assert role is not None

            user = User(
                email=f"{code.lower()}-{batch}@stad.local",
                full_name=f"STAD Test {code}",
                password_hash=hash_password(password),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                token_version=1,
            )

            db.add(user)
            db.flush()

            tokens[code] = create_access_token(
                user_id=user.id,
                token_version=user.token_version,
            )

            if code == "ADMIN":
                admin_id = user.id

        db.commit()

    yield {
        "batch": batch,
        "tokens": tokens,
        "admin_id": admin_id,
        "password": password,
    }

    with SessionLocal() as db:
        user_ids = db.scalars(
            select(User.id).where(
                User.email.like(f"%-{batch}@stad.local")
            )
        ).all()

        if user_ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.user_id.in_(user_ids)
                )
            )

            db.execute(
                delete(User).where(
                    User.id.in_(user_ids)
                )
            )

        db.commit()


def valid_payload(context, role="ENGINEER"):
    return {
        "email": f"new-{context['batch']}@stad.local",
        "full_name": "STAD New User",
        "role": role,
        "temporary_password": context["password"],
    }


def csrf_headers(client):
    response = client.get("/api/v1/auth/csrf")

    assert response.status_code == 200

    return {
        "X-CSRF-Token": response.json()["csrf_token"]
    }


def post_with_role(context, role, payload, use_csrf=True):
    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            context["tokens"][role],
        )

        headers = (
            csrf_headers(client)
            if use_csrf
            else {}
        )

        return client.post(
            USERS_URL,
            json=payload,
            headers=headers,
        )


def test_create_user_requires_authentication(user_context):
    with TestClient(app) as client:
        response = client.post(
            USERS_URL,
            json=valid_payload(user_context),
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["ENGINEER", "VIEWER"],
)

def test_only_admin_can_create_users(user_context, role):
    response = post_with_role(
        user_context,
        role,
        valid_payload(user_context),
    )

    assert response.status_code == 403


def test_create_user_requires_csrf(user_context):
    response = post_with_role(
        user_context,
        "ADMIN",
        valid_payload(user_context),
        use_csrf=False,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Invalid CSRF token"
    )


@pytest.mark.parametrize(
    "role",
    ["ENGINEER", "VIEWER"],
)

def test_admin_can_create_user(user_context, role):
    payload = valid_payload(user_context, role)

    response = post_with_role(
        user_context,
        "ADMIN",
        payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == payload["email"]
    assert data["role"] == role
    assert data["is_active"] is True
    assert data["must_change_password"] is True
    assert "password_hash" not in data
    assert "temporary_password" not in data

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.email == payload["email"]
            )
        )

        assert user is not None

        assert user.password_hash != (
            payload["temporary_password"]
        )

        assert verify_password(
            payload["temporary_password"],
            user.password_hash,
        )

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "USER_CREATED",
                AuditLog.user_id == user_context["admin_id"],
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(user.id),
            )
        )

        assert audit is not None
        assert audit.details["role"] == role
        assert "temporary_password" not in audit.details


def test_duplicate_email_returns_409(user_context):
    payload = valid_payload(user_context)

    first = post_with_role(
        user_context,
        "ADMIN",
        payload,
    )

    second = post_with_role(
        user_context,
        "ADMIN",
        payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "Email already registered"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid-email"},
        {"full_name": "   "},
        {"temporary_password": "short"},
        {"role": "ADMIN"},
        {"role": "UNKNOWN"},
    ],
)
def test_invalid_user_data_returns_422(
    user_context,
    changes,
):
    payload = valid_payload(user_context)
    payload.update(changes)

    response = post_with_role(
        user_context,
        "ADMIN",
        payload,
    )

    assert response.status_code == 422


def test_new_user_must_change_password(user_context):
    payload = valid_payload(user_context, "VIEWER")

    created = post_with_role(
        user_context,
        "ADMIN",
        payload,
    )

    assert created.status_code == 201

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": payload["email"],
                "password": payload["temporary_password"],
            },
            headers=csrf_headers(client),
        )

        assert response.status_code == 200
        assert response.json()["must_change_password"] is True

        dashboard = client.get(
            "/api/v1/dashboard/summary"
        )

        assert dashboard.status_code == 403
        assert dashboard.json()["detail"] == (
            "Password change required"
        )

        new_password = "NewSecurePassword-2026!"

        changed = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": payload["temporary_password"],
                "new_password": new_password,
            },
            headers=csrf_headers(client),
        )

        assert changed.status_code == 200
        assert changed.json()["login_required"] is True

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 401

        login_again = client.post(
            "/api/v1/auth/login",
            json={
                "email": payload["email"],
                "password": new_password,
            },
            headers=csrf_headers(client),
        )

        assert login_again.status_code == 200
        assert (
            login_again.json()["must_change_password"]
            is False
        )

        dashboard = client.get(
            "/api/v1/dashboard/summary"
        )

        assert dashboard.status_code == 200