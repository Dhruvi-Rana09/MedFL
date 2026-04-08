"""Model Storage Service — stores global model snapshots per aggregation round."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List

from schemas import StoreRequest, StoreResponse, LoadResponse
import storage

app = FastAPI(
    title="MedFL Model Storage Service",
    description="Stores and retrieves global model weights after each FedAvg round.",
)

# Allow Streamlit dashboard & other services to call these APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "model-storage", "status": "running"}


@app.post("/store", response_model=StoreResponse)
def store_model(req: StoreRequest):
    """Store model weights for a given aggregation round."""
    storage.save_model(
        round_number=req.round_number,
        weights=req.weights,
        accuracy=req.accuracy,
    )
    return StoreResponse(round_number=req.round_number)


@app.get("/load")
def load_model(round: Optional[int] = Query(None, description="Round number to load. Omit for latest.")):
    """Load model weights — latest by default, or for a specific round."""
    if round is not None:
        record = storage.load_by_round(round)
        if record is None:
            raise HTTPException(status_code=404, detail=f"No model found for round {round}")
        return record

    record = storage.load_latest()
    if record is None:
        raise HTTPException(status_code=404, detail="No models stored yet")
    return record


@app.get("/history")
def get_history():
    """Return the full model history across all rounds (for dashboard charts)."""
    return storage.load_all()