from fastapi import FastAPI
import os

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
from auth_client import require_auth

app = FastAPI()
stored_model = {}

@app.post("/store")
@require_auth(AUTH_URL)
def store(model: dict):
    global stored_model
    stored_model = model
    return {"status": "stored"}

@app.get("/load")
@require_auth(AUTH_URL)
def load():
    return stored_model