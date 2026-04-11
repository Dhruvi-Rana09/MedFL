"""
Shared auth dependency for MedFL services.
Each service imports require_auth and uses it as a FastAPI dependency.
The public key is fetched once from Auth service and cached forever.
"""
import os, httpx
from fastapi import HTTPException, Header
from jose import jwt, JWTError

_cached_pub_key: str | None = None

async def _fetch_public_key() -> str:
    global _cached_pub_key
    if not _cached_pub_key:
        async with httpx.AsyncClient() as c:
            resp = await c.get(f"{os.environ['AUTH_URL']}/auth/public-key")
            _cached_pub_key = resp.json()["public_key"]
    return _cached_pub_key

async def require_auth(authorization: str = Header(...)) -> str:
    """FastAPI dependency — use with Depends(require_auth)"""
    token = authorization.replace("Bearer ", "")
    try:
        key     = await _fetch_public_key()
        payload = jwt.decode(token, key, algorithms=["RS256"])
        return payload["sub"]  # returns hospital_id
    except (JWTError, Exception):
        raise HTTPException(401, "Invalid or expired token")

async def verify_grpc_token(token: str, hospital_id: str) -> bool:
    """For gRPC handlers — returns True/False instead of raising."""
    try:
        key     = await _fetch_public_key()
        payload = jwt.decode(token, key, algorithms=["RS256"])
        return payload["sub"] == hospital_id
    except:
        return False