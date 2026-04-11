"""Pydantic schemas for the Monitoring (Logging) Service."""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class LogEntry(BaseModel):
    """Request body for POST /log."""
    event: str
    source: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class LogRecord(BaseModel):
    """A stored log record with metadata."""
    id: int
    event: str
    source: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str


class LogResponse(BaseModel):
    """Response for POST /log."""
    status: str = "logged"
    id: int
