"""Aggregator Service — receives hospital updates and performs FedAvg aggregation."""

from fastapi import FastAPI
import requests

app = FastAPI(
    title="MedFL Aggregator Service",
    description="Central aggregator for federated learning — collects updates and runs FedAvg.",
)

global_model = {"weights": [0.5, 0.5]}
updates = []
current_round = 0

# Service URLs (Docker service names)
STORAGE_URL = "http://storage:8000"
MONITOR_URL = "http://monitor:8000"


def _log_event(event: str, source: str = "aggregator", details: dict = None):
    """Send a log event to the monitoring service (fire-and-forget)."""
    try:
        requests.post(f"{MONITOR_URL}/log", json={
            "event": event,
            "source": source,
            "details": details,
        }, timeout=3)
    except Exception:
        pass  # Don't let logging failures break aggregation


def _store_model(round_number: int, weights: list, accuracy: float = None):
    """Persist the global model snapshot to the storage service."""
    try:
        requests.post(f"{STORAGE_URL}/store", json={
            "round_number": round_number,
            "weights": weights,
            "accuracy": accuracy,
        }, timeout=3)
    except Exception:
        pass  # Don't let storage failures break aggregation


# ---- Byzantine fault detection ----
MALICIOUS_THRESHOLD = 100.0  # Weights above this are considered malicious


def _is_malicious(weights: list) -> bool:
    """Detect suspicious weight updates (e.g., [999, 999])."""
    return any(abs(w) > MALICIOUS_THRESHOLD for w in weights)


@app.get("/")
def root():
    return {"message": "Aggregator Running"}


@app.post("/receive-update")
def receive_update(update: dict):
    weights = update.get("weights", [])
    hospital = update.get("hospital_id", "unknown")

    # Byzantine fault tolerance — reject malicious updates
    if _is_malicious(weights):
        _log_event(
            event=f"Malicious update REJECTED from {hospital}",
            details={"hospital_id": hospital, "weights": weights},
        )
        return {"status": "rejected", "reason": "malicious weights detected"}

    updates.append(weights)
    _log_event(
        event=f"Hospital update received from {hospital}",
        details={"hospital_id": hospital, "weight_count": len(weights)},
    )
    return {"status": "received"}


@app.get("/aggregate")
def aggregate():
    global global_model, current_round

    if not updates:
        return {"message": "No updates to aggregate"}

    # FedAvg — average all received weight vectors
    avg = [sum(x) / len(x) for x in zip(*updates)]
    current_round += 1
    global_model["weights"] = avg
    updates.clear()

    # Simulated accuracy (in a real system this would come from evaluation)
    simulated_accuracy = round(0.5 + (current_round * 0.05) + (sum(avg) / len(avg) * 0.1), 4)

    # Persist to storage service
    _store_model(
        round_number=current_round,
        weights=avg,
        accuracy=simulated_accuracy,
    )

    # Log the aggregation event
    _log_event(
        event=f"Aggregation completed for round {current_round}",
        details={
            "round": current_round,
            "accuracy": simulated_accuracy,
            "num_updates": len(avg),
        },
    )

    return {
        "global_model": global_model,
        "round": current_round,
        "accuracy": simulated_accuracy,
    }


@app.get("/send-model")
def send_model():
    _log_event(event="Global model sent to requesting hospital")
    return global_model