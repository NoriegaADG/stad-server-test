
from fastapi import FastAPI, HTTPException
from app.db import check_database_connection


# Configuración principal de STAD
app = FastAPI(
    title="STAD API",
    description="Server Test Automation Dashboard",
    version="1.1.0",
)


# Verifica que FastAPI esté funcionando
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "stad-backend",
    }


# Verifica la conexión con PostgreSQL
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