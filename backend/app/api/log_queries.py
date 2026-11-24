
from datetime import datetime
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db import get_db
from app.models import TestExecution

router = APIRouter(
    prefix="/logs",
    tags=["Logs"],
    dependencies=[
        Depends(require_roles(
            "ADMIN", "ENGINEER", "VIEWER"
        ))
    ],
)

class ExecutionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_name: str
    filename: str
    sha256: str
    file_size_bytes: int
    result: str
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: int | None
    uploaded_by_user_id: int
    created_at: datetime

class ExecutionPage(BaseModel):
    items: list[ExecutionListItem]
    total: int
    page: int
    page_size: int

@router.get("", response_model=ExecutionPage)
def list_executions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    node_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    result: Literal[
        "PASS", "FAIL", "ERROR", "INCOMPLETE"
    ] | None = Query(default=None),
    started_from: datetime | None = Query(default=None),
    started_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    for value in (started_from, started_to):
        if value is not None and value.utcoffset() is None:
            raise HTTPException(
                status_code=422,
                detail="Date filters require a UTC offset",
            )

    if (
        started_from is not None
        and started_to is not None
        and started_from > started_to
    ):
        raise HTTPException(
            status_code=422,
            detail="started_from must not exceed started_to",
        )

    filters = []

    if node_name is not None:
        filters.append(
            TestExecution.node_name == node_name
        )

    if result is not None:
        filters.append(
            TestExecution.result == result
        )

    if started_from is not None:
        filters.append(
            TestExecution.started_at >= started_from
        )

    if started_to is not None:
        filters.append(
            TestExecution.started_at <= started_to
        )

    total = db.scalar(
        select(func.count())
        .select_from(TestExecution)
        .where(*filters)
    ) or 0

    records = db.scalars(
        select(TestExecution)
        .where(*filters)
        .order_by(
            TestExecution.started_at.desc(),
            TestExecution.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ExecutionPage(
        items=[
            ExecutionListItem.model_validate(record)
            for record in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{execution_id}",
    response_model=ExecutionListItem,
)
def get_execution(
    execution_id: int = Path(ge=1),
    db: Session = Depends(get_db),
):
    execution = db.get(
        TestExecution,
        execution_id,
    )

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail="Execution not found",
        )

    return ExecutionListItem.model_validate(
        execution
    )