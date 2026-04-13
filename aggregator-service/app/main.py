# from fastapi import FastAPI
# import requests

# app = FastAPI()

# global_model = {"weights": [0.5, 0.5]}

# updates = []

# @app.get("/")
# def root():
#     return {"message": "Aggregator Running"}

# @app.post("/receive-update")
# def receive_update(update: dict):
#     updates.append(update["weights"])
#     return {"status": "received"}

# @app.get("/aggregate")
# def aggregate():
#     global global_model
#     if not updates:
#         return {"message": "No updates"}

#     avg = [sum(x)/len(x) for x in zip(*updates)]
#     global_model["weights"] = avg
#     updates.clear()

#     return {"global_model": global_model}

# @app.get("/send-model")
# def send_model():
#     return global_model


# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from app.fedavg import federated_averaging, is_malicious
# from app.config import MIN_UPDATES_TO_AGGREGATE

# app = FastAPI(title="Aggregator Service")

# # In-memory storage
# pending_updates: list[dict] = []
# global_model: dict = {"weights": [0.0] * 10, "round": 0}


# class ModelUpdate(BaseModel):
#     hospital_id: str
#     weights: list[float]
#     num_samples: int


# # ─── Health Check ─────────────────────────────────
# @app.get("/health")
# def health():
#     return {
#         "status": "ok",
#         "pending_updates": len(pending_updates),
#         "current_round": global_model["round"]
#     }


# # ─── Receive Update from Hospital ─────────────────
# @app.post("/receive-update")
# def receive_update(update: ModelUpdate):

#     # Byzantine check
#     if is_malicious(update.weights):
#         return {
#             "status": "rejected",
#             "reason": "malicious update detected",
#             "hospital_id": update.hospital_id
#         }

#     # Accept update
#     pending_updates.append({
#         "hospital_id": update.hospital_id,
#         "weights": update.weights,
#         "num_samples": update.num_samples
#     })

#     return {
#         "status": "accepted",
#         "hospital_id": update.hospital_id,
#         "total_pending": len(pending_updates)
#     }


# # ─── Aggregate All Updates ─────────────────────────
# @app.post("/aggregate")
# def aggregate():
#     if len(pending_updates) < MIN_UPDATES_TO_AGGREGATE:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Need at least {MIN_UPDATES_TO_AGGREGATE} updates, currently have {len(pending_updates)}"
#         )

#     # Run FedAvg
#     new_weights = federated_averaging(pending_updates)
#     global_model["weights"] = new_weights
#     global_model["round"] += 1

#     hospitals_included = [u["hospital_id"] for u in pending_updates]
#     pending_updates.clear()

#     return {
#         "status": "aggregated",
#         "round": global_model["round"],
#         "hospitals_included": hospitals_included,
#         "weights_preview": global_model["weights"][:3]
#     }


# # ─── Send Global Model ─────────────────────────────
# @app.get("/send-model")
# def send_model():
#     return global_model

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio

from app.fedavg import federated_averaging, is_malicious
from app.config import MIN_UPDATES_TO_AGGREGATE, HOSPITAL_URLS
from auth_client import require_auth
import os

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")   

MODEL_STORAGE_URL = "http://storage:8000" 

app = FastAPI(title="Aggregator Service")

pending_updates: list[dict] = []
global_model: dict = {"weights": [0.0] * 10, "round": 0}


class ModelUpdate(BaseModel):
    hospital_id: str
    weights: list[float]
    num_samples: int

# ─── 🔁 LOAD MODEL FROM STORAGE ON STARTUP ─────────────────────
@app.on_event("startup")
async def load_latest_model():
    global global_model
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MODEL_STORAGE_URL}/latest", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                global_model["weights"] = data["weights"]
                global_model["round"] = data["version"]
                print(f"[Aggregator] Loaded model v{data['version']} from storage")
    except Exception as e:
        print(f"[Aggregator] No stored model found, starting fresh ({e})")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "pending_updates": len(pending_updates),
        "current_round": global_model["round"]
    }



@app.post("/receive-update")
@require_auth(AUTH_URL)
def receive_update(update: ModelUpdate):
    if is_malicious(update.weights):
        return {
            "status": "rejected",
            "reason": "malicious update detected",
            "hospital_id": update.hospital_id
        }

    pending_updates.append({
        "hospital_id": update.hospital_id,
        "weights": update.weights,
        "num_samples": update.num_samples
    })

    return {
        "status": "accepted",
        "hospital_id": update.hospital_id,
        "total_pending": len(pending_updates)
    }


async def _push_global_model_to_hospitals(weights: list[float], round_num: int):
    """Fire-and-forget: push the new global model to every hospital."""
    payload = {"weights": weights}

    async def push_one(url: str):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{url}/receive-model",
                    json=payload,
                    timeout=10.0
                )
                print(f"[Aggregator] Pushed to {url} → {resp.status_code}")
        except Exception as e:
            
            print(f"[Aggregator] Failed to push to {url}: {e}")

    await asyncio.gather(*[push_one(url) for url in HOSPITAL_URLS])


@app.post("/aggregate")
@require_auth(AUTH_URL)
async def aggregate():
    if len(pending_updates) < MIN_UPDATES_TO_AGGREGATE:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {MIN_UPDATES_TO_AGGREGATE} updates, currently have {len(pending_updates)}"
        )

    new_weights = federated_averaging(pending_updates)

    global_model["weights"] = new_weights
    global_model["round"] += 1

    current_round = global_model["round"]
    hospitals_included = [u["hospital_id"] for u in pending_updates]

    pending_updates.clear()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MODEL_STORAGE_URL}/save",
                json={
                    "weights": global_model["weights"],
                    "version": current_round
                },
                timeout=5.0
            )
            print(f"[Aggregator] Model v{current_round} saved → {resp.status_code}")
    except Exception as e:
        print(f"[Aggregator] Failed to save model: {e}")

    await _push_global_model_to_hospitals(global_model["weights"], current_round)

    return {
        "status": "aggregated",
        "round": current_round,
        "hospitals_included": hospitals_included,
        "weights_preview": global_model["weights"][:3]
    }

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
@require_auth(AUTH_URL)
def send_model():
    _log_event(event="Global model sent to requesting hospital")
    return global_model