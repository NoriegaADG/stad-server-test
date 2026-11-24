
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db import get_db
from app.models import TestExecution

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[
        Depends(
            require_roles(
                "ADMIN",
                "ENGINEER",
                "VIEWER",
            )
        )
    ],
)

class DashboardSummary(BaseModel):
    total_executions: int
    pass_count: int
    fail_count: int
    error_count: int
    incomplete_count: int
    success_rate_percent: float
    average_duration_seconds: float | None

@router.get(
    "/summary",
    response_model=DashboardSummary,
)

def get_dashboard_summary(
    node_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
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

    if started_from is not None:
        filters.append(
            TestExecution.started_at >= started_from
        )

    if started_to is not None:
        filters.append(
            TestExecution.started_at <= started_to
        )

    query = select(
        func.count(TestExecution.id),
        func.count(TestExecution.id).filter(
            TestExecution.result == "PASS"
        ),
        func.count(TestExecution.id).filter(
            TestExecution.result == "FAIL"
        ),
        func.count(TestExecution.id).filter(
            TestExecution.result == "ERROR"
        ),
        func.count(TestExecution.id).filter(
            TestExecution.result == "INCOMPLETE"
        ),
        func.avg(TestExecution.duration_seconds),
    ).where(*filters)

    (
        total,
        passed,
        failed,
        errors,
        incomplete,
        average_duration,
    ) = db.execute(query).one()

    success_rate = (
        round((passed / total) * 100, 2)
        if total > 0
        else 0.0
    )

    return DashboardSummary(
        total_executions=total,
        pass_count=passed,
        fail_count=failed,
        error_count=errors,
        incomplete_count=incomplete,
        success_rate_percent=success_rate,
        average_duration_seconds=(
            round(float(average_duration), 2)
            if average_duration is not None
            else None
        ),
    )