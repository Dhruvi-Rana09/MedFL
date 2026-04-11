from fastapi import FastAPI
import os

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
from auth_client import require_auth

app = FastAPI()

logs = []

@app.post("/log")
@require_auth(AUTH_URL)
def log(data: dict):
    logs.append(data)
    return {"status": "logged"}

@app.get("/logs")
@require_auth(AUTH_URL)
def get_logs():
    return logs