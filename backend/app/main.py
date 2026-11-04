
from fastapi import FastAPI

app = FastAPI(
    title="STAD API",
    description="Server Test Automation Dashboard",
    version="1.1.0",
)

@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "stad-backend",
    }
