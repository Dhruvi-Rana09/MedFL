"""
main.py — MedFL Orchestrator REST API.

Provides:
  - /rounds/start      — start a new training round
  - /rounds/auto       — run N rounds automatically
  - /rounds/status     — current round state
  - /rounds/history    — completed round metrics
  - /rounds/metrics    — detailed per-round metrics
  - /hospitals         — list connected hospital statuses
  - /health            — health check
"""

import os
import asyncio
import logging
from typing import List
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.round_manager import RoundManager, RoundState
from app.grpc_server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

# Config from Environment
AGG_URL = os.environ.get("AGG_URL", "http://aggregation:8000")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MONITORING_URL = os.environ.get("MONITORING_URL", "http://monitoring:8000")
AUTH_URL = os.environ.get("AUTH_URL", "http://auth:8000")
MINIO_USER = os.environ.get("MINIO_USER", "minioadmin")
MINIO_PASS = os.environ.get("MINIO_PASS", "minioadmin")

os.environ["MINIO_ACCESS_KEY"] = MINIO_USER
os.environ["MINIO_SECRET_KEY"] = MINIO_PASS

manager = RoundManager(
    agg_url=AGG_URL,
    registry_url=MINIO_ENDPOINT,
    monitoring_url=MONITORING_URL,
)

# Hospital endpoint registry (Dynamically populated)
HOSPITAL_ENDPOINTS = {}

_grpc_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _grpc_task

    # Load latest global model checkpoint
    ckpt = manager.load_latest_checkpoint()
    if ckpt is not None:
        manager.global_model = ckpt
        logger.info("Loaded latest global model checkpoint from storage.")

    # Start gRPC server
    _grpc_task = asyncio.create_task(serve(manager, port=50051))

    yield

    logger.info("Orchestrator shutting down")
    if _grpc_task:
        _grpc_task.cancel()


app = FastAPI(title="MedFL Orchestrator REST API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRoundRequest(BaseModel):
    hospital_ids: List[str] = []
    algorithm: str = "fedprox"


class AutoRoundRequest(BaseModel):
    n_rounds: int = 5
    hospital_ids: List[str] = []
    algorithm: str = "fedprox"


class HospitalRegisterRequest(BaseModel):
    hospital_id: str
    url: str


@app.post("/hospitals/register")
async def register_hospital(req: HospitalRegisterRequest):
    """Dynamically register a hospital node."""
    HOSPITAL_ENDPOINTS[req.hospital_id] = req.url
    logger.info("Registered hospital: %s at %s", req.hospital_id, req.url)
    return {"status": "registered", "hospital_id": req.hospital_id, "url": req.url}

@app.post("/rounds/start")
async def start_round(req: StartRoundRequest):
    """Initiate a new training round and trigger hospitals."""
    if manager.state not in (RoundState.IDLE, RoundState.DONE):
        raise HTTPException(status_code=409, detail="Round already in progress")

    if not req.hospital_ids:
        req.hospital_ids = list(HOSPITAL_ENDPOINTS.keys())
        if not req.hospital_ids:
            raise HTTPException(status_code=400, detail="No hospitals registered")

    os.environ["AGGREGATION_ALGORITHM"] = req.algorithm
    manager.start_round(req.hospital_ids)

    # Actually trigger hospital training via HTTP
    triggered = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for hid in req.hospital_ids:
            url = HOSPITAL_ENDPOINTS.get(hid)
            if not url:
                logger.warning("No endpoint registered for %s", hid)
                continue
            try:
                resp = await client.post(f"{url}/train/trigger")
                resp.raise_for_status()
                triggered.append(hid)
                logger.info("Triggered training on %s", hid)
            except Exception as e:
                logger.error("Failed to trigger %s: %s", hid, e)

    return {
        "round_id": manager.current_round,
        "status": "started",
        "participants": req.hospital_ids,
        "triggered": triggered,
        "algorithm": req.algorithm,
    }


@app.post("/rounds/auto")
async def auto_rounds(req: AutoRoundRequest):
    """Run N training rounds automatically with delays."""
    if manager.state not in (RoundState.IDLE, RoundState.DONE):
        raise HTTPException(status_code=409, detail="Round already in progress")

    if not req.hospital_ids:
        req.hospital_ids = list(HOSPITAL_ENDPOINTS.keys())
        if not req.hospital_ids:
            raise HTTPException(status_code=400, detail="No hospitals registered")

    os.environ["AGGREGATION_ALGORITHM"] = req.algorithm

    async def _run_auto():
        for i in range(req.n_rounds):
            logger.info("=== Auto Round %d/%d ===", i + 1, req.n_rounds)

            # Wait for any in-progress round to finish
            while manager.state not in (RoundState.IDLE, RoundState.DONE):
                await asyncio.sleep(1)

            manager.start_round(req.hospital_ids)

            # Trigger all hospitals
            async with httpx.AsyncClient(timeout=10.0) as client:
                for hid in req.hospital_ids:
                    url = HOSPITAL_ENDPOINTS.get(hid)
                    if url:
                        try:
                            await client.post(f"{url}/train/trigger")
                        except Exception as e:
                            logger.error("Failed to trigger %s: %s", hid, e)

            # Wait for round completion
            timeout = 300  # 5 min max
            elapsed = 0
            while manager.state != RoundState.DONE and elapsed < timeout:
                await asyncio.sleep(2)
                elapsed += 2

            if manager.state != RoundState.DONE:
                logger.error("Round %d timed out", manager.current_round)
                break

            # Brief cooldown between rounds
            await asyncio.sleep(2)

    asyncio.create_task(_run_auto())

    return {
        "status": "auto_training_started",
        "n_rounds": req.n_rounds,
        "algorithm": req.algorithm,
        "participants": req.hospital_ids,
    }


@app.get("/rounds/status")
async def get_status():
    """Check real-time progress of the current round."""
    return {
        "round": manager.current_round,
        "state": manager.state.value,
        "updates_received": len(manager.updates),
        "waiting_for": len(manager.selected),
        "hospital_metrics": manager.hospital_metrics,
    }


@app.get("/rounds/history")
async def get_history():
    """All completed round metrics."""
    return {"rounds": manager.round_history}


@app.get("/rounds/metrics")
async def get_metrics():
    """Detailed metrics for dashboard."""
    return {
        "current_round": manager.current_round,
        "state": manager.state.value,
        "algorithm": os.environ.get("AGGREGATION_ALGORITHM", "fedprox"),
        "rounds": manager.round_history,
        "hospital_metrics": manager.hospital_metrics,
    }


@app.get("/hospitals")
async def list_hospitals():
    """Check status of all registered hospital nodes."""
    statuses = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for hid, url in HOSPITAL_ENDPOINTS.items():
            try:
                resp = await client.get(f"{url}/status")
                resp.raise_for_status()
                data = resp.json()
                from urllib.parse import urlparse
                data["ip_address"] = urlparse(url).hostname if url else "local"
                statuses[hid] = data
            except Exception:
                from urllib.parse import urlparse
                ip = urlparse(url).hostname if url else "unknown"
                statuses[hid] = {"status": "unreachable", "hospital_id": hid, "ip_address": ip}
    return statuses


@app.post("/rounds/reset")
async def reset_round():
    """Force-reset a stuck round back to DONE state."""
    if manager.state in (RoundState.IDLE, RoundState.DONE):
        return {"status": "already_idle", "round": manager.current_round}

    old_state = manager.state.value
    manager.state = RoundState.DONE
    manager.updates.clear()
    logger.warning(
        "Force-reset round %d from state '%s' to DONE",
        manager.current_round, old_state,
    )
    return {
        "status": "reset",
        "round": manager.current_round,
        "previous_state": old_state,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "grpc_port": 50051, "round": manager.current_round}
