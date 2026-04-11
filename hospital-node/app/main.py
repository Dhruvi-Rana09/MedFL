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

# ─── Receive Global Model (push FROM aggregator) ─────────────
@app.post("/receive-model")
async def receive_model(model: GlobalModel):
    print(f"[{HOSPITAL_ID}] Received global model: {model.weights[:3]}...")
    return {
        "status": "model_received",
        "hospital_id": HOSPITAL_ID,
        "weights_preview": model.weights[:3]
    }

# ─── Fetch Global Model (pull BY hospital) ───────────────────
@app.get("/fetch-model")
async def fetch_global_model():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AGGREGATOR_URL}/send-model",
                timeout=10.0
            )
            response.raise_for_status()
            model = response.json()
            print(f"[{HOSPITAL_ID}] Fetched global model round {model.get('round')}: {model['weights'][:3]}...")
            return {
                "status": "model_fetched",
                "hospital_id": HOSPITAL_ID,
                "round": model.get("round"),
                "weights_preview": model["weights"][:3]
            }
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Aggregator unreachable: {str(e)}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Aggregator error: {e.response.text}")