
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)

from pydantic import BaseModel

from app.api.auth import csrf_session_id
from app.api.deps import require_roles
from app.core.csrf import require_csrf
from app.services.log_upload_validator import (
    MAX_LOG_FILE_BYTES,
    validate_log_file,
)

router = APIRouter(
    prefix="/logs",
    tags=["Logs"],
    dependencies=[
        Depends(require_roles("ADMIN", "ENGINEER"))
    ],
)

class LogUploadResponse(BaseModel):
    filename: str
    size_bytes: int
    sha256: str
    node_name: str
    result: str
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    saved: bool

@router.post(
    "/upload",
    response_model=LogUploadResponse,
)

async def upload_log(
    request: Request,
    file: UploadFile = File(...),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    try:
        content = await file.read(
            MAX_LOG_FILE_BYTES + 1
        )
    finally:
        await file.close()

    if len(content) > MAX_LOG_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Log file exceeds 20 MB",
        )

    try:
        validated = validate_log_file(
            filename=file.filename or "",
            content=content,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    summary = validated.summary

    return LogUploadResponse(
        filename=validated.filename,
        size_bytes=validated.size_bytes,
        sha256=validated.sha256,
        node_name=summary.node_name,
        result=summary.result,
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        duration_seconds=(
            summary.duration.total_seconds()
            if summary.duration is not None
            else None
        ),
        saved=False,
    )