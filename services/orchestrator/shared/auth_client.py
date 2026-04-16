"""
shared/auth_client.py — Shared JWT authentication dependency for MedFL services.

This module is copied into every non-auth service's Docker build context so
they can validate JWT tokens locally, without importing the auth service's
code or making per-request calls to it.

How it works:
  1. On first use, fetches the RS256 public key from the Auth service
     (via the GET /auth/public-key endpoint).
  2. Caches the key in a module-level variable — never re-fetched.
  3. All subsequent token validations are pure local crypto (no network).

Provides two entry points:
  • require_auth()       — async FastAPI dependency for REST endpoints
  • verify_grpc_token()  — async helper for gRPC service handlers

Environment variables:
  AUTH_URL  — base URL of the Auth service (e.g. http://auth:8000)
"""

import os
import logging
from typing import Optional

import httpx
from fastapi import Header, HTTPException
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# ── Module-level cache ───────────────────────────────────────────────────────
_cached_public_key: Optional[str] = None
_ALGORITHM = "RS256"


async def _fetch_public_key() -> str:
    """Fetch and cache the RS256 public key from the Auth service.

    Called once on the first token validation; all later calls return
    the cached value immediately.
    """
    global _cached_public_key

    if _cached_public_key is not None:
        return _cached_public_key

    auth_url = os.environ.get("AUTH_URL", "http://auth:8000")
    url = f"{auth_url}/auth/public-key"
    logger.info("Fetching public key from %s …", url)

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

    _cached_public_key = data["public_key"]
    logger.info("Public key cached (algorithm=%s)", data.get("algorithm", _ALGORITHM))
    return _cached_public_key


# ── FastAPI dependency ───────────────────────────────────────────────────────

async def require_auth(authorization: str = Header(...)) -> str:
    """FastAPI dependency — validates a Bearer JWT and returns the hospital_id.

    Usage::

        @app.get("/protected")
        async def protected(hospital_id: str = Depends(require_auth)):
            ...

    Raises:
        HTTPException 401 on missing, malformed, expired, or invalid tokens.
    """
    # Strip "Bearer " prefix
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        public_key = await _fetch_public_key()
        payload = jwt.decode(token, public_key, algorithms=[_ALGORITHM])
        hospital_id: str = payload.get("sub", "")
        if not hospital_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return hospital_id
    except (JWTError, httpx.HTTPError, KeyError, Exception):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── gRPC helper ──────────────────────────────────────────────────────────────

async def verify_grpc_token(token: str, hospital_id: str) -> bool:
    """Validate a JWT and confirm it belongs to the claimed hospital.

    Returns True if the token is valid **and** ``payload["sub"]`` matches
    the provided ``hospital_id``.  Returns False on any failure — gRPC
    handlers should translate this into an UNAUTHENTICATED status code
    rather than raising Python exceptions.
    """
    try:
        public_key = await _fetch_public_key()
        payload = jwt.decode(token, public_key, algorithms=[_ALGORITHM])
        return payload.get("sub") == hospital_id
    except Exception:
        return False
