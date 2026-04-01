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


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.fedavg import federated_averaging, is_malicious
from app.config import MIN_UPDATES_TO_AGGREGATE

app = FastAPI(title="Aggregator Service")

# In-memory storage
pending_updates: list[dict] = []
global_model: dict = {"weights": [0.0] * 10, "round": 0}


class ModelUpdate(BaseModel):
    hospital_id: str
    weights: list[float]
    num_samples: int


# ─── Health Check ─────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "pending_updates": len(pending_updates),
        "current_round": global_model["round"]
    }


# ─── Receive Update from Hospital ─────────────────
@app.post("/receive-update")
def receive_update(update: ModelUpdate):

    # Byzantine check
    if is_malicious(update.weights):
        return {
            "status": "rejected",
            "reason": "malicious update detected",
            "hospital_id": update.hospital_id
        }

    # Accept update
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


# ─── Aggregate All Updates ─────────────────────────
@app.post("/aggregate")
def aggregate():
    if len(pending_updates) < MIN_UPDATES_TO_AGGREGATE:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {MIN_UPDATES_TO_AGGREGATE} updates, currently have {len(pending_updates)}"
        )

    # Run FedAvg
    new_weights = federated_averaging(pending_updates)
    global_model["weights"] = new_weights
    global_model["round"] += 1

    hospitals_included = [u["hospital_id"] for u in pending_updates]
    pending_updates.clear()

    return {
        "status": "aggregated",
        "round": global_model["round"],
        "hospitals_included": hospitals_included,
        "weights_preview": global_model["weights"][:3]
    }


# ─── Send Global Model ─────────────────────────────
@app.get("/send-model")
def send_model():
    return global_model
