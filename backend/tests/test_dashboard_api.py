
import hashlib

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.db import SessionLocal, engine
from app.main import app
from app.models import (
    Role,
    TestExecution as ExecutionRecord,
    User,
)

SUMMARY_URL = "/api/v1/dashboard/summary"

@pytest.fixture
def dashboard_data():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    batch = uuid4().hex
    node_a = f"NODE{batch[:10]}"
    node_b = f"NODE{batch[10:20]}"

    with SessionLocal() as db:
        users = {}

        for role_code in ("ADMIN", "ENGINEER", "VIEWER"):
            role = db.scalar(
                select(Role).where(
                    Role.code == role_code
                )
            )

            assert role is not None

            user = User(
                email=f"{role_code.lower()}-{batch}@stad.local",
                full_name=f"STAD Dashboard {role_code}",
                password_hash=hash_password(
                    "TestPasswordOnly-2026!"
                ),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                token_version=1,
            )

            db.add(user)
            users[role_code] = user

        db.flush()

        tokens = {
            role_code: create_access_token(
                user_id=user.id,
                token_version=user.token_version,
            )
            for role_code, user in users.items()
        }

        results = [
            "PASS",
            "PASS",
            "FAIL",
            "ERROR",
            "INCOMPLETE",
        ]

        durations = [60, 120, 180, 240, None]

        base_time = datetime(
            2026, 11, 11, 10, 0,
            tzinfo=timezone.utc,
        )

        executions = []

        for index, (result, duration) in enumerate(
            zip(results, durations)
        ):
            started_at = base_time + timedelta(
                days=index
            )

            execution = ExecutionRecord(
                node_name=(
                    node_a if index < 3 else node_b
                ),
                filename=f"dashboard_{index}.log",
                sha256=hashlib.sha256(
                    f"{batch}-{index}".encode()
                ).hexdigest(),
                file_size_bytes=175,
                result=result,
                started_at=started_at,
                finished_at=(
                    started_at + timedelta(seconds=duration)
                    if duration is not None
                    else None
                ),
                duration_seconds=duration,
                uploaded_by_user_id=users["ENGINEER"].id,
            )

            db.add(execution)
            executions.append(execution)

        db.flush()

        execution_ids = [
            execution.id for execution in executions
        ]

        user_ids = [
            user.id for user in users.values()
        ]

        db.commit()

    yield {
        "tokens": tokens,
        "node_a": node_a,
        "node_b": node_b,
    }

    with SessionLocal() as db:
        db.execute(
            delete(ExecutionRecord).where(
                ExecutionRecord.id.in_(execution_ids)
            )
        )

        db.execute(
            delete(User).where(
                User.id.in_(user_ids)
            )
        )

        db.commit()


def get_summary(
    token: str | None = None,
    query: str = "",
):
    with TestClient(app) as client:
        if token is not None:
            client.cookies.set(
                "stad_access_token",
                token,
            )

        return client.get(SUMMARY_URL + query)


def test_summary_requires_authentication():
    response = get_summary()

    assert response.status_code == 401

@pytest.mark.parametrize(
    "role",
    ["ADMIN", "ENGINEER", "VIEWER"],
)
def test_summary_allowed_roles(dashboard_data, role):
    response = get_summary(
        dashboard_data["tokens"][role]
    )

    assert response.status_code == 200
    assert "total_executions" in response.json()


def test_summary_calculates_statistics(dashboard_data):
    response = get_summary(
        dashboard_data["tokens"]["ADMIN"]
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_executions"] == 5
    assert data["pass_count"] == 2
    assert data["fail_count"] == 1
    assert data["error_count"] == 1
    assert data["incomplete_count"] == 1

    assert data["success_rate_percent"] == 40.0
    assert data["average_duration_seconds"] == 150.0


def test_summary_filters_by_node(dashboard_data):
    node = dashboard_data["node_a"]

    response = get_summary(
        dashboard_data["tokens"]["VIEWER"],
        f"?node_name={node}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_executions"] == 3
    assert data["pass_count"] == 2
    assert data["fail_count"] == 1
    assert data["error_count"] == 0
    assert data["incomplete_count"] == 0

    assert data["success_rate_percent"] == 66.67
    assert data["average_duration_seconds"] == 120.0


def test_summary_filters_by_dates(dashboard_data):
    response = get_summary(
        dashboard_data["tokens"]["ENGINEER"],
        "?started_from=2026-11-12T00:00:00Z"
        "&started_to=2026-11-13T23:59:59Z",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_executions"] == 2
    assert data["pass_count"] == 1
    assert data["fail_count"] == 1

    assert data["success_rate_percent"] == 50.0
    assert data["average_duration_seconds"] == 150.0


def test_summary_no_matching_records(dashboard_data):
    response = get_summary(
        dashboard_data["tokens"]["VIEWER"],
        "?node_name=NODE_NOT_FOUND",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_executions"] == 0
    assert data["pass_count"] == 0
    assert data["fail_count"] == 0
    assert data["error_count"] == 0
    assert data["incomplete_count"] == 0

    assert data["success_rate_percent"] == 0.0
    assert data["average_duration_seconds"] is None


@pytest.mark.parametrize(
    "query",
    [
        "?node_name=",
        "?started_from=2026-11-11T10:00:00",
        "?started_to=2026-11-13T10:00:00",
        (
            "?started_from=2026-11-14T00:00:00Z"
            "&started_to=2026-11-13T00:00:00Z"
        ),
        "?started_from=invalid",
    ],
)
def test_summary_rejects_invalid_filters(
    dashboard_data,
    query,
):
    response = get_summary(
        dashboard_data["tokens"]["ENGINEER"],
        query,
    )

    assert response.status_code == 422