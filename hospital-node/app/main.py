# from fastapi import FastAPI
# import requests
# import random

# app = FastAPI()

# AGGREGATOR_URL = "http://aggregator:8000"

# @app.get("/")
# def root():
#     return {"message": "Hospital Node Running"}

# @app.get("/train")
# def train():
#     # Fake training (simulate ML)
#     weights = [random.random(), random.random()]

#     requests.post(f"{AGGREGATOR_URL}/receive-update",
#                   json={"weights": weights})

#     return {"trained_weights": weights}

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

from app.train import local_train
from app.config import AGGREGATOR_URL, HOSPITAL_ID

app = FastAPI(title="Hospital Node Service")

class GlobalModel(BaseModel):
    weights: list[float]

# ─── Health Check ───────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "hospital_id": HOSPITAL_ID}

# ─── Train & Send Update ────────────────────────────────────
@app.post("/train")
async def train_and_send():
    """
    1. Run local training
    2. Send weights to aggregator
    """
    weights, num_samples = local_train()

    payload = {
        "hospital_id": HOSPITAL_ID,
        "weights": weights,
        "num_samples": num_samples
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AGGREGATOR_URL}/receive-update",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Aggregator unreachable: {str(e)}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Aggregator error: {e.response.text}")

    return {
        "status": "update_sent",
        "hospital_id": HOSPITAL_ID,
        "weights_sent": weights,
        "num_samples": num_samples,
        "aggregator_response": response.json()
    }

# ─── Receive Global Model ────────────────────────────────────
@app.post("/receive-model")
async def receive_model(model: GlobalModel):
    """
    Called by Aggregator to push the updated global model back.
    """
    # In real FL: load these weights into your local model
    print(f"[{HOSPITAL_ID}] Received global model: {model.weights[:3]}...")
    return {
        "status": "model_received",
        "hospital_id": HOSPITAL_ID,
        "weights_preview": model.weights[:3]
    }