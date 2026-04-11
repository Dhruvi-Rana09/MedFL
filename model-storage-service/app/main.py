from fastapi import FastAPI,  HTTPException
from app.storage import save_model, load_model, list_versions
import os

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
from auth_client import require_auth

app = FastAPI()


@app.get("/")
@require_auth(AUTH_URL)
def health():
    return {"status": "Model Storage Service Running"}


@app.post("/store")
@require_auth(AUTH_URL)
def store(model: dict):
    version = save_model(model)

    return {
        "message": "Model stored successfully",
        "version": version
    }


@app.get("/load")
@require_auth(AUTH_URL)
def load(version: int = None):
    data = load_model(version)

    if data is None:
        raise HTTPException(status_code=404, detail="Model not found")

    return data


@app.get("/versions")
@require_auth(AUTH_URL)
def versions():
    return {"available_versions": list_versions()}
