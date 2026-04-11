"""Pydantic schemas for the Model Storage Service."""

from pydantic import BaseModel
from typing import Optional, List


class StoreRequest(BaseModel):
    """Request body for POST /store."""
    round_number: int
    weights: List[float]
    accuracy: Optional[float] = None


class ModelRecord(BaseModel):
    """A stored model record with metadata."""
    round_number: int
    weights: List[float]
    accuracy: Optional[float] = None
    timestamp: str


class StoreResponse(BaseModel):
    """Response for POST /store."""
    status: str = "stored"
    round_number: int


class LoadResponse(BaseModel):
    """Response for GET /load — returns a single model record."""
    round_number: int
    weights: List[float]
    accuracy: Optional[float] = None
    timestamp: str
