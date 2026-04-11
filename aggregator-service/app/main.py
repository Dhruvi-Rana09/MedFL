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
<<<<<<< HEAD
from app.config import MIN_UPDATES_TO_AGGREGATE
from auth_client import require_auth
import os

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")   
=======
from app.config import MIN_UPDATES_TO_AGGREGATE, HOSPITAL_URLS
>>>>>>> 6c3da512fe41a8dc25eac7b4469618c1558ca93f

app = FastAPI(title="Aggregator Service")

pending_updates: list[dict] = []
global_model: dict = {"weights": [0.0] * 10, "round": 0}


class ModelUpdate(BaseModel):
    hospital_id: str
    weights: list[float]
    num_samples: int


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
            # Log but don't fail — a hospital being down shouldn't break aggregation
            print(f"[Aggregator] Failed to push to {url}: {e}")

    await asyncio.gather(*[push_one(url) for url in HOSPITAL_URLS])


@app.post("/aggregate")
<<<<<<< HEAD
@require_auth(AUTH_URL)
def aggregate():
=======
async def aggregate():                          # note: now async
>>>>>>> 6c3da512fe41a8dc25eac7b4469618c1558ca93f
    if len(pending_updates) < MIN_UPDATES_TO_AGGREGATE:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {MIN_UPDATES_TO_AGGREGATE} updates, currently have {len(pending_updates)}"
        )

    new_weights = federated_averaging(pending_updates)
    global_model["weights"] = new_weights
    global_model["round"] += 1

    hospitals_included = [u["hospital_id"] for u in pending_updates]
    pending_updates.clear()

    # Push global model back to all hospitals
    await _push_global_model_to_hospitals(global_model["weights"], global_model["round"])

    return {
        "status": "aggregated",
        "round": global_model["round"],
        "hospitals_included": hospitals_included,
        "weights_preview": global_model["weights"][:3]
    }


@app.get("/send-model")
@require_auth(AUTH_URL)
def send_model():
    return global_model