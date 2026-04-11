from fastapi import FastAPI
import os

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
from auth_client import require_auth

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List

from schemas import LogEntry, LogRecord, LogResponse
import logger

app = FastAPI(
    title="MedFL Monitoring Service",
    description="Centralized logging for federated learning events (training, aggregation, faults).",
)

# Allow Streamlit dashboard & other services to call these APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@require_auth(AUTH_URL)
def root():
    return {"service": "monitoring", "status": "running"}


@app.post("/log", response_model=LogResponse)
@require_auth(AUTH_URL)
def create_log(entry: LogEntry):
    """Log a system event (e.g., training started, aggregation completed, malicious node detected)."""
    record = logger.add_log(
        event=entry.event,
        source=entry.source,
        details=entry.details,
    )
    return LogResponse(id=record["id"])


@app.get("/logs", response_model=List[LogRecord])
@require_auth(AUTH_URL)
def get_logs(
    limit: Optional[int] = Query(None, description="Max number of logs to return"),
    source: Optional[str] = Query(None, description="Filter by source (e.g., 'aggregator', 'hospital')"),
):
    """Retrieve system logs, newest first. Optionally filter by source and limit count."""
    return logger.get_logs(limit=limit, source=source)
