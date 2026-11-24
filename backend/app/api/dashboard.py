
from datetime import date, datetime

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


class NodeStatistics(BaseModel):
    node_name: str
    total_executions: int
    pass_count: int
    fail_count: int
    error_count: int
    incomplete_count: int
    success_rate_percent: float
    average_duration_seconds: float | None

class NodeStatisticsPage(BaseModel):
    items: list[NodeStatistics]
    total_nodes: int
    page: int
    page_size: int


@router.get(
    "/nodes",
    response_model=NodeStatisticsPage,
)

def get_node_statistics(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
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

    if started_from is not None:
        filters.append(
            TestExecution.started_at >= started_from
        )

    if started_to is not None:
        filters.append(
            TestExecution.started_at <= started_to
        )

    total_nodes = db.scalar(
        select(
            func.count(
                func.distinct(TestExecution.node_name)
            )
        ).where(*filters)
    ) or 0

    query = (
        select(
            TestExecution.node_name.label("node_name"),
            func.count(TestExecution.id).label(
                "total_executions"
            ),
            func.count(TestExecution.id).filter(
                TestExecution.result == "PASS"
            ).label("pass_count"),
            func.count(TestExecution.id).filter(
                TestExecution.result == "FAIL"
            ).label("fail_count"),
            func.count(TestExecution.id).filter(
                TestExecution.result == "ERROR"
            ).label("error_count"),
            func.count(TestExecution.id).filter(
                TestExecution.result == "INCOMPLETE"
            ).label("incomplete_count"),
            func.avg(
                TestExecution.duration_seconds
            ).label("average_duration"),
        )
        .where(*filters)
        .group_by(TestExecution.node_name)
        .order_by(TestExecution.node_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = db.execute(query).all()

    items = []

    for row in rows:
        success_rate = round(
            (row.pass_count / row.total_executions) * 100,
            2,
        )

        items.append(
            NodeStatistics(
                node_name=row.node_name,
                total_executions=row.total_executions,
                pass_count=row.pass_count,
                fail_count=row.fail_count,
                error_count=row.error_count,
                incomplete_count=row.incomplete_count,
                success_rate_percent=success_rate,
                average_duration_seconds=(
                    round(float(row.average_duration), 2)
                    if row.average_duration is not None
                    else None
                ),
            )
        )

    return NodeStatisticsPage(
        items=items,
        total_nodes=total_nodes,
        page=page,
        page_size=page_size,
    )


class DailyTrend(BaseModel):
    day: date
    total_executions: int
    pass_count: int
    fail_count: int
    error_count: int
    incomplete_count: int
    success_rate_percent: float


class DailyTrendPage(BaseModel):
    items: list[DailyTrend]
    total_days: int
    page: int
    page_size: int


@router.get(
    "/trends",
    response_model=DailyTrendPage,
)
def get_daily_trends(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    node_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    started_from: datetime | None = Query(default=None),
    started_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    # Validar que las fechas incluyan zona horaria.
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

    # Agrupar siempre por fecha UTC.
    day_bucket = func.date(
        func.timezone(
            "UTC",
            TestExecution.started_at,
        )
    )

    # Contar días diferentes para la paginación.
    total_days = db.scalar(
        select(
            func.count(
                func.distinct(day_bucket)
            )
        )
        .select_from(TestExecution)
        .where(*filters)
    ) or 0

    query = (
        select(
            day_bucket.label("day"),
            func.count(TestExecution.id).label(
                "total_executions"
            ),
            func.count(TestExecution.id).filter(
                TestExecution.result == "PASS"
            ).label("pass_count"),
            func.count(TestExecution.id).filter(
                TestExecution.result == "FAIL"
            ).label("fail_count"),
            func.count(TestExecution.id).filter(
                TestExecution.result == "ERROR"
            ).label("error_count"),
            func.count(TestExecution.id).filter(
                TestExecution.result == "INCOMPLETE"
            ).label("incomplete_count"),
        )
        .where(*filters)
        .group_by(day_bucket)
        .order_by(day_bucket.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = db.execute(query).all()

    items = []

    for row in rows:
        success_rate = round(
            (row.pass_count / row.total_executions) * 100,
            2,
        )

        items.append(
            DailyTrend(
                day=row.day,
                total_executions=row.total_executions,
                pass_count=row.pass_count,
                fail_count=row.fail_count,
                error_count=row.error_count,
                incomplete_count=row.incomplete_count,
                success_rate_percent=success_rate,
            )
        )

    return DailyTrendPage(
        items=items,
        total_days=total_days,
        page=page,
        page_size=page_size,
    )
