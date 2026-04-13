from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import bcrypt, os, redis as redis_lib
from .jwt_utils import create_token, verify_token, revoke_token, PUBLIC_KEY

app = FastAPI(title="MedFL Auth Service")

# Allow all origins in dev (tighten in production)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

r   = redis_lib.from_url(os.environ["REDIS_URL"])
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Request / Response models ──
class RegisterRequest(BaseModel):
    hospital_id: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ── Endpoints ──

@app.post("/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    # Check if already registered
    if r.get(f"hospital:{req.hospital_id}"):
        raise HTTPException(409, "Hospital already registered")
    
    # Hash the password before storing (NEVER store plain text)
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt())
    r.set(f"hospital:{req.hospital_id}", hashed)
    
    # Return a fresh JWT token
    return TokenResponse(access_token=create_token(req.hospital_id))

@app.post("/auth/login", response_model=TokenResponse)
async def login(req: RegisterRequest):
    stored = r.get(f"hospital:{req.hospital_id}")
    if not stored:
        raise HTTPException(401, "Hospital not found")
    if not bcrypt.checkpw(req.password.encode(), stored):
        raise HTTPException(401, "Wrong password")
    return TokenResponse(access_token=create_token(req.hospital_id))

@app.get("/auth/public-key")
async def get_public_key():
    # Other services call this once to cache the public key
    return {"public_key": PUBLIC_KEY, "algorithm": "RS256"}

@app.post("/auth/revoke")
async def revoke(token: str = Depends(oauth2)):
    revoke_token(token)
    return {"revoked": True}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}
