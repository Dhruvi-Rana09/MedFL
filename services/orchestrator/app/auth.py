"""
auth.py — JWT verification for the Orchestrator service.

Fetches the public key from the Auth service on first call,
then caches it for subsequent verifications.
"""

import logging
from typing import Optional

import httpx
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.AUTH_SERVICE_URL}/auth/login")

# ── Cached public key ────────────────────────────────────────────────────────
_cached_public_key: Optional[str] = None
_cached_algorithm: str = "RS256"


async def _fetch_public_key() -> str:
    """Fetch the RS256 public key from the Auth service."""
    global _cached_public_key, _cached_algorithm

    if _cached_public_key is not None:
        return _cached_public_key

    url = f"{settings.AUTH_SERVICE_URL}/auth/public-key"
    logger.info("Fetching public key from %s", url)

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

    _cached_public_key = data["public_key"]
    _cached_algorithm = data.get("algorithm", "RS256")
    logger.info("Public key cached (algorithm=%s)", _cached_algorithm)
    return _cached_public_key


async def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — returns the hospital_id from a valid JWT.

    Raises HTTPException 401 on invalid / expired tokens.
    """
    public_key = await _fetch_public_key()

    try:
        payload = jwt.decode(token, public_key, algorithms=[_cached_algorithm])
        hospital_id: str = payload.get("sub")
        if hospital_id is None:
            raise HTTPException(status_code=401, detail="Token missing 'sub' claim")
        return hospital_id
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def invalidate_key_cache() -> None:
    """Force re-fetch of the public key on next verification."""
    global _cached_public_key
    _cached_public_key = None
