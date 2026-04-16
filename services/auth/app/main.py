"""
main.py — MedFL Auth Service (SVC-1).

Provides hospital registration, login, token revocation,
and a public-key endpoint so every other service can verify JWTs.
"""

import os
import logging

import bcrypt
import redis
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.jwt_utils import create_token, verify_token, revoke_token

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="MedFL Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Redis helper ─────────────────────────────────────────────────────────────

def _get_redis() -> redis.Redis:
    return redis.from_url(os.environ["REDIS_URL"])

# ── Pydantic models ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    hospital_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    """Register a new hospital (or update password) and return a JWT.

    Uses upsert semantics: if the hospital_id already exists in Redis,
    the password hash is overwritten with the new password.  This avoids
    stale bcrypt-hash mismatches that occur when containers are rebuilt
    while the Redis volume persists.
    """
    r = _get_redis()
    key = f"hospital:{body.hospital_id}"

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt())
    is_new = not r.exists(key)
    r.set(key, hashed)

    token = create_token(body.hospital_id)

    if not is_new:
        logger.info("Re-registered %s (password hash updated)", body.hospital_id)

    return TokenResponse(access_token=token)


@app.post("/auth/login", response_model=TokenResponse)
def login(body: RegisterRequest):
    """Authenticate a hospital and return a fresh JWT."""
    r = _get_redis()
    stored = r.get(f"hospital:{body.hospital_id}")

    if stored is None:
        raise HTTPException(status_code=401, detail="Hospital not found")

    if not bcrypt.checkpw(body.password.encode(), stored):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token(body.hospital_id)
    return TokenResponse(access_token=token)


@app.get("/auth/public-key")
def public_key():
    """Serve the RS256 public key so other services can verify tokens."""
    path = os.environ.get("JWT_PUBLIC_KEY_PATH", "certs/public.pem")
    with open(path, "r") as f:
        pem = f.read()
    return {"public_key": pem, "algorithm": "RS256"}


@app.post("/auth/revoke")
def revoke(token: str = Depends(oauth2_scheme)):
    """Revoke the caller's current token."""
    revoke_token(token)
    return {"revoked": True}


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}


# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _on_startup():
    logger.info("Auth service ready on port 8000")
