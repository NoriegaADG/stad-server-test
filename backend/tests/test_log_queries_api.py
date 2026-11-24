
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

LIST_URL = "/api/v1/logs"

@pytest.fixture
def query_data():
    assert engine.url.database == "stad_test"
    assert engine.url.host == "db_test"

    batch = uuid4().hex
    node = f"NODE{batch[:10]}"
    other_node = f"NODE{batch[10:20]}"

    with SessionLocal() as db:
        users = {}

        for code in ("ADMIN", "ENGINEER", "VIEWER"):
            role = db.scalar(
                select(Role).where(Role.code == code)
            )

            assert role is not None

            user = User(
                email=f"{code.lower()}-{batch}@stad.local",
                full_name=f"STAD Query {code}",
                password_hash=hash_password(
                    "TestPasswordOnly-2026!"
                ),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                token_version=1,
            )

            db.add(user)
            users[code] = user

        db.flush()

        tokens = {
            code: create_access_token(
                user_id=user.id,
                token_version=user.token_version,
            )
            for code, user in users.items()
        }

        base_time = datetime(
            2026, 11, 11, 10, 0,
            tzinfo=timezone.utc,
        )

        results = [
            "PASS",
            "FAIL",
            "ERROR",
            "INCOMPLETE",
        ]

        executions = []

        for index, result in enumerate(results):
            started_at = base_time + timedelta(
                days=index
            )

            execution = ExecutionRecord(
                node_name=(
                    node if index < 2 else other_node
                ),
                filename=f"query_{index}.log",
                sha256=hashlib.sha256(
                    f"{batch}-{index}".encode()
                ).hexdigest(),
                file_size_bytes=175,
                result=result,
                started_at=started_at,
                finished_at=(
                    started_at + timedelta(minutes=2)
                    if result != "INCOMPLETE"
                    else None
                ),
                duration_seconds=(
                    120 if result != "INCOMPLETE"
                    else None
                ),
                uploaded_by_user_id=users["ENGINEER"].id,
            )

            db.add(execution)
            executions.append(execution)

        db.commit()

        execution_ids = [
            execution.id for execution in executions
        ]
        user_ids = [
            user.id for user in users.values()
        ]

    yield {
        "tokens": tokens,
        "node": node,
        "other_node": other_node,
        "ids": execution_ids,
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


def get_list(token: str, query: str = ""):
    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        return client.get(LIST_URL + query)


def get_detail(
    token: str,
    execution_id: int | str,
):
    with TestClient(app) as client:
        client.cookies.set(
            "stad_access_token",
            token,
        )

        return client.get(
            f"{LIST_URL}/{execution_id}"
        )


def test_list_requires_authentication():
    with TestClient(app) as client:
        response = client.get(LIST_URL)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["ADMIN", "ENGINEER", "VIEWER"],
)
def test_roles_can_list_executions(query_data, role):
    response = get_list(
        query_data["tokens"][role]
    )

    assert response.status_code == 200
    assert "items" in response.json()


def test_filter_by_node(query_data):
    response = get_list(
        query_data["tokens"]["VIEWER"],
        f"?node_name={query_data['node']}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2

    assert all(
        item["node_name"] == query_data["node"]
        for item in data["items"]
    )


def test_pagination_and_order(query_data):
    token = query_data["tokens"]["ENGINEER"]
    node = query_data["node"]

    first = get_list(
        token,
        f"?node_name={node}&page=1&page_size=1",
    )

    second = get_list(
        token,
        f"?node_name={node}&page=2&page_size=1",
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_data = first.json()
    second_data = second.json()

    assert first_data["total"] == 2
    assert second_data["total"] == 2
    assert len(first_data["items"]) == 1
    assert len(second_data["items"]) == 1

    assert (
        first_data["items"][0]["id"]
        == query_data["ids"][1]
    )

    assert (
        second_data["items"][0]["id"]
        == query_data["ids"][0]
    )


def test_filter_by_result(query_data):
    response = get_list(
        query_data["tokens"]["VIEWER"],
        "?result=ERROR"
        f"&node_name={query_data['other_node']}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["result"] == "ERROR"


def test_filter_by_dates(query_data):
    response = get_list(
        query_data["tokens"]["ENGINEER"],
        f"?node_name={query_data['node']}"
        "&started_from=2026-11-12T00:00:00Z"
        "&started_to=2026-11-12T23:59:59Z",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["result"] == "FAIL"


def test_empty_page(query_data):
    response = get_list(
        query_data["tokens"]["VIEWER"],
        f"?node_name={query_data['node']}"
        "&page=3&page_size=1",
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    "query",
    [
        "?page=0",
        "?page_size=101",
        "?result=UNKNOWN",
        "?started_from=2026-11-11T10:00:00",
        (
            "?started_from=2026-11-13T00:00:00Z"
            "&started_to=2026-11-12T00:00:00Z"
        ),
    ],
)
def test_invalid_filters_return_422(
    query_data,
    query,
):
    response = get_list(
        query_data["tokens"]["ENGINEER"],
        query,
    )

    assert response.status_code == 422


def test_detail_requires_authentication():
    with TestClient(app) as client:
        response = client.get(
            f"{LIST_URL}/1"
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["ADMIN", "ENGINEER", "VIEWER"],
)
def test_detail_allowed_roles(query_data, role):
    execution_id = query_data["ids"][0]

    response = get_detail(
        query_data["tokens"][role],
        execution_id,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == execution_id
    assert data["node_name"] == query_data["node"]
    assert data["result"] == "PASS"
    assert data["duration_seconds"] == 120


def test_detail_incomplete_execution(query_data):
    execution_id = query_data["ids"][3]

    response = get_detail(
        query_data["tokens"]["VIEWER"],
        execution_id,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["result"] == "INCOMPLETE"
    assert data["finished_at"] is None
    assert data["duration_seconds"] is None


def test_detail_not_found(query_data):
    nonexistent_id = (
        max(query_data["ids"]) + 1_000_000
    )

    response = get_detail(
        query_data["tokens"]["ENGINEER"],
        nonexistent_id,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Execution not found"
    )


@pytest.mark.parametrize(
    "invalid_id",
    [0, -1, "abc"],
)
def test_detail_invalid_id(
    query_data,
    invalid_id,
):
    response = get_detail(
        query_data["tokens"]["ADMIN"],
        invalid_id,
    )

    assert response.status_code == 422