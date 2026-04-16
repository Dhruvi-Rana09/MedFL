"""
MedFL Monitoring & Audit Service

Receives round metrics from the orchestrator, stores them in-memory,
exposes via Prometheus gauges, REST endpoints, and SSE for real-time dashboard.
Serves the professional monitoring dashboard at /.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="MedFL Monitoring & Audit Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus gauges and counters ──────────────────────────────────────────
global_accuracy    = Gauge("medfl_global_accuracy",     "Global model accuracy",  ["round", "algorithm"])
global_loss        = Gauge("medfl_global_loss",          "Global model loss",      ["round", "algorithm"])
ish_weight_gauge   = Gauge("medfl_ish_weight",           "DWFed/FedProx ISH weight", ["hospital", "round"])
round_duration     = Gauge("medfl_round_duration_sec",   "Round wall-clock time",  ["round"])
rounds_completed   = Counter("medfl_rounds_completed",   "Total completed rounds")
participants_per_round = Gauge("medfl_participants",     "Hospitals per round",    ["round"])

# ── In-memory storage ───────────────────────────────────────────────────────
round_history: List[dict] = []
audit_log: List[dict] = []
hospital_history: Dict[str, List[dict]] = {}  # hospital_id -> list of per-round metrics
sse_subscribers: List[asyncio.Queue] = []

# ── Pydantic Schemas ────────────────────────────────────────────────────────
class RoundMetrics(BaseModel):
    round_id: int
    algorithm: str
    accuracy: float = 0.0
    loss: float = 0.0
    duration_sec: float = 0.0
    participants: List[str]
    ish_weights: Dict[str, float] = {}
    hospital_metrics: Dict[str, Dict[str, float]] = {}


# ── SSE Broadcast ───────────────────────────────────────────────────────────
async def _broadcast_event(event_type: str, data: dict):
    """Send an SSE event to all connected dashboard clients."""
    message = json.dumps({"type": event_type, **data})
    dead = []
    for q in sse_subscribers:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        sse_subscribers.remove(q)


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.post("/metrics/round")
async def log_round(metrics: RoundMetrics):
    """Log metrics for a completed training round."""
    r_id_str = str(metrics.round_id)
    algo = metrics.algorithm

    global_accuracy.labels(round=r_id_str, algorithm=algo).set(metrics.accuracy)
    global_loss.labels(round=r_id_str, algorithm=algo).set(metrics.loss)
    round_duration.labels(round=r_id_str).set(metrics.duration_sec)
    participants_per_round.labels(round=r_id_str).set(len(metrics.participants))

    for h, w in metrics.ish_weights.items():
        ish_weight_gauge.labels(hospital=h, round=r_id_str).set(w)

    rounds_completed.inc()

    timestamp = datetime.now(timezone.utc).isoformat()

    record = metrics.model_dump()
    record["timestamp"] = timestamp
    round_history.append(record)

    # Track per-hospital metrics
    for h_id, h_metrics in metrics.hospital_metrics.items():
        if h_id not in hospital_history:
            hospital_history[h_id] = []
        hospital_history[h_id].append({
            "round_id": metrics.round_id,
            "accuracy": h_metrics.get("accuracy", 0.0),
            "loss": h_metrics.get("loss", 0.0),
            "n_samples": h_metrics.get("n_samples", 0),
            "timestamp": timestamp,
        })

    audit_entry = {
        "event": "round_complete",
        "round_id": metrics.round_id,
        "algorithm": algo,
        "accuracy": metrics.accuracy,
        "loss": metrics.loss,
        "hospitals": metrics.participants,
        "encryption": "AES-Fernet",
        "timestamp": timestamp,
    }
    audit_log.append(audit_entry)

    # Broadcast to SSE subscribers
    await _broadcast_event("round_complete", {
        "round_id": metrics.round_id,
        "accuracy": metrics.accuracy,
        "loss": metrics.loss,
        "algorithm": algo,
        "duration_sec": metrics.duration_sec,
        "participants": metrics.participants,
        "ish_weights": metrics.ish_weights,
        "hospital_metrics": metrics.hospital_metrics,
        "timestamp": timestamp,
    })

    return {"logged": True, "round_id": metrics.round_id}


@app.get("/metrics/history")
def get_history(algo: Optional[str] = None):
    """Get all round history, optionally filtered by algorithm."""
    if algo:
        return [r for r in round_history if r.get("algorithm") == algo]
    return round_history


@app.get("/metrics/hospitals")
def get_hospital_metrics():
    """Per-hospital training metrics across all rounds."""
    return hospital_history


@app.get("/metrics/convergence")
def get_convergence():
    """Convergence data formatted for charts."""
    rounds = []
    accuracies = []
    losses = []
    algorithms = []

    for r in round_history:
        rounds.append(r["round_id"])
        accuracies.append(r.get("accuracy", 0.0))
        losses.append(r.get("loss", 0.0))
        algorithms.append(r.get("algorithm", "unknown"))

    return {
        "rounds": rounds,
        "accuracies": accuracies,
        "losses": losses,
        "algorithms": algorithms,
    }


@app.get("/metrics/summary")
def get_summary():
    """Dashboard summary statistics."""
    fedavg_rounds = sum(1 for r in round_history if r.get("algorithm") == "fedavg")
    dwfed_rounds = sum(1 for r in round_history if r.get("algorithm") == "dwfed")
    fedprox_rounds = sum(1 for r in round_history if r.get("algorithm") == "fedprox")
    latest_acc = round_history[-1].get("accuracy", 0.0) if round_history else 0.0
    latest_loss = round_history[-1].get("loss", 0.0) if round_history else 0.0
    algos = list(set(r.get("algorithm") for r in round_history if r.get("algorithm")))

    best_acc = max((r.get("accuracy", 0.0) for r in round_history), default=0.0)

    return {
        "total_rounds": len(round_history),
        "algorithms_used": algos,
        "latest_accuracy": latest_acc,
        "latest_loss": latest_loss,
        "best_accuracy": best_acc,
        "fedavg_rounds": fedavg_rounds,
        "dwfed_rounds": dwfed_rounds,
        "fedprox_rounds": fedprox_rounds,
        "active_hospitals": len(hospital_history),
        "total_audit_events": len(audit_log),
    }


@app.get("/audit/log")
def get_audit_log():
    """HIPAA-style audit log of all round events."""
    return audit_log


@app.get("/metrics/live")
async def sse_stream(request: Request):
    """Server-Sent Events stream for real-time dashboard updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_subscribers.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": "update", "data": data}
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": "{}"}
        finally:
            if queue in sse_subscribers:
                sse_subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus scrape endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "ok", "rounds_logged": len(round_history)}


# ── Dashboard Static Files ──────────────────────────────────────────────────
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"

if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard")

@app.get("/", response_class=HTMLResponse)
async def dashboard_root():
    """Serve the monitoring dashboard."""
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>MedFL Monitoring — Dashboard not found</h1>")
