"""
main.py — MedFL Hospital Node REST API.

Provides:
  - Lifespan auto-registration with the auth service
  - /train/trigger  — kick off a local training round via gRPC
  - /status         — current training status
  - /metrics        — training history for dashboard
  - /health         — health check
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.grpc_client import participate_in_round
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

HOSPITAL_ID = settings.HOSPITAL_ID
AUTH_URL = settings.AUTH_SERVICE_URL
HOSPITAL_PASSWORD = settings.HOSPITAL_PASSWORD

current_token: Optional[str] = None
training_status: str = "idle"
training_history: List[Dict[str, Any]] = []
last_accuracy: float = 0.0
last_loss: float = 0.0
rounds_completed: int = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global current_token
    # Register (upsert) on startup — always returns a fresh token
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(5):
            try:
                response = await client.post(
                    f"{AUTH_URL}/auth/register",
                    json={"hospital_id": HOSPITAL_ID, "password": HOSPITAL_PASSWORD}
                )
                response.raise_for_status()
                current_token = response.json()["access_token"]
                logger.info("[%s] Authenticated — token acquired", HOSPITAL_ID)
                break
            except Exception as e:
                logger.warning("[%s] Startup auth attempt %d failed: %s", HOSPITAL_ID, attempt + 1, e)
                if attempt < 4:
                    await asyncio.sleep(3)
    yield


app = FastAPI(title=f"MedFL Hospital Node ({HOSPITAL_ID})", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/train/trigger")
async def trigger_train():
    """Trigger a local training round via gRPC."""
    global training_status
    if training_status == "training":
        raise HTTPException(status_code=409, detail="Already training")

    if current_token is None:
        raise HTTPException(status_code=503, detail="Not authenticated yet")

    training_status = "training"
    asyncio.create_task(_run_training())
    return {"status": "training_started", "hospital_id": HOSPITAL_ID}


async def _run_training():
    """Background task to execute training and record results."""
    global training_status, last_accuracy, last_loss, rounds_completed
    try:
        result = await participate_in_round(current_token)
        training_status = "done"
        last_accuracy = result.get("accuracy", 0.0)
        last_loss = result.get("loss", 0.0)
        rounds_completed += 1
        training_history.append({
            "round_id": result.get("round_id", 0),
            "accuracy": last_accuracy,
            "loss": last_loss,
            "n_samples": result.get("n_samples", 0),
            "label_dist": result.get("label_dist", []),
        })
        logger.info(
            "[%s] Round %d complete: acc=%.4f loss=%.4f",
            HOSPITAL_ID, result.get("round_id", 0), last_accuracy, last_loss,
        )
    except Exception as e:
        logger.error("[%s] Training error: %s", HOSPITAL_ID, e)
        training_status = "error"


@app.get("/status")
async def status():
    """Current training status and last known metrics."""
    return {
        "hospital_id": HOSPITAL_ID,
        "status": training_status,
        "token_set": current_token is not None,
        "rounds_completed": rounds_completed,
        "last_accuracy": last_accuracy,
        "last_loss": last_loss,
    }


@app.get("/metrics")
async def metrics():
    """Training history for dashboard consumption."""
    return {
        "hospital_id": HOSPITAL_ID,
        "rounds_completed": rounds_completed,
        "last_accuracy": last_accuracy,
        "last_loss": last_loss,
        "dp_epsilon": settings.DP_EPSILON,
        "dp_delta": settings.DP_DELTA,
        "fedprox_mu": settings.FEDPROX_MU,
        "encryption_enabled": bool(settings.ENCRYPTION_KEY),
        "history": training_history,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "hospital_id": HOSPITAL_ID}
