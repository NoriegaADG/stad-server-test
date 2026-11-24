
from fastapi import FastAPI, HTTPException

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.db import check_database_connection
from app.api.audit import router as audit_router
from app.api.logs import router as logs_router
from app.api.log_queries import router as log_queries_router

app = FastAPI(
    title="STAD API",
    description="Server Test Automation Dashboard",
    version="1.1.0",
)

app.include_router(
    auth_router,
    prefix="/api/v1/auth",
)

app.include_router(
    users_router,
    prefix="/api/v1",
)

app.include_router(
    audit_router,
    prefix="/api/v1"
)

app.include_router(
    logs_router,
    prefix="/api/v1",
)

app.include_router(
    log_queries_router,
    prefix="/api/v1",
)

@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "stad-backend",
    }

@app.get("/api/v1/health/db", tags=["Health"])
def database_health_check():
    try:
        check_database_connection()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

    return {
        "status": "ok",
        "database": "connected",
    }
