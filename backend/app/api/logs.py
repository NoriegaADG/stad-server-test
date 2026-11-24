
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
from sqlalchemy.orm import Session

from app.api.auth import csrf_session_id
from app.api.deps import require_roles
from app.core.csrf import require_csrf
from app.db import get_db
from app.models import User

from app.services.log_upload_validator import (
    MAX_LOG_FILE_BYTES,
    validate_log_file,
)
from app.services.test_execution_service import (
    DuplicateExecutionError,
    save_test_execution,
)

router = APIRouter(
    prefix="/logs",
    tags=["Logs"],
)


class LogUploadResponse(BaseModel):
    id: int
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
    status_code=201,
)

def upload_log(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    uploader: User = Depends(
        require_roles("ADMIN", "ENGINEER")
    ),
):
    require_csrf(
        request,
        csrf_session_id(request),
    )

    try:
        content = file.file.read(
            MAX_LOG_FILE_BYTES + 1
        )
    finally:
        file.file.close()

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

    ip_address = (
        request.client.host
        if request.client is not None
        else None
    )

    try:
        execution = save_test_execution(
            db=db,
            validated_log=validated,
            uploaded_by_user_id=uploader.id,
            ip_address=ip_address,
        )

    except DuplicateExecutionError as exc:
        raise HTTPException(
            status_code=409,
            detail="A log with this SHA-256 already exists",
        ) from exc

    return LogUploadResponse(
        id=execution.id,
        filename=execution.filename,
        size_bytes=execution.file_size_bytes,
        sha256=execution.sha256,
        node_name=execution.node_name,
        result=execution.result,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        duration_seconds=execution.duration_seconds,
        saved=True,
    )