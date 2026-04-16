"""
jwt_utils.py — JWT creation, verification, and revocation for MedFL.

Tokens are RS256-signed JWTs with a 24-hour lifetime.
Revocation is tracked in Redis with a matching 24h TTL.
"""

import os
from datetime import datetime, timedelta, timezone

import redis
from jose import jwt

# ── Configuration ────────────────────────────────────────────────────────────
_ALGORITHM = "RS256"
_TOKEN_LIFETIME = timedelta(hours=24)
_REVOKE_TTL = 86_400  # seconds — matches token lifetime


def _load_key(env_var: str, default: str) -> str:
    """Read a PEM key file from the path specified by an env var."""
    path = os.environ.get(env_var, default)
    with open(path, "r") as f:
        return f.read()


def _get_redis() -> redis.Redis:
    """Return a Redis client from the REDIS_URL env var."""
    return redis.from_url(os.environ["REDIS_URL"])


# ── Public API ───────────────────────────────────────────────────────────────

def create_token(hospital_id: str) -> str:
    """Create an RS256-signed JWT for the given hospital.

    Payload:
        sub  – hospital_id
        iat  – UTC now
        exp  – UTC now + 24 h
    """
    private_key = _load_key("JWT_PRIVATE_KEY_PATH", "certs/private.pem")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": hospital_id,
        "iat": now,
        "exp": now + _TOKEN_LIFETIME,
    }

    return jwt.encode(payload, private_key, algorithm=_ALGORITHM)


def verify_token(token: str) -> str:
    """Verify a JWT and return the hospital_id (``sub`` claim).

    Raises:
        ValueError  – if the token has been revoked.
        jose.JWTError – if the signature or expiry is invalid (propagates).
    """
    r = _get_redis()

    # Check the revocation list
    if r.exists(f"revoked:{token}"):
        raise ValueError("Token revoked")

    public_key = _load_key("JWT_PUBLIC_KEY_PATH", "certs/public.pem")

    payload = jwt.decode(token, public_key, algorithms=[_ALGORITHM])
    return payload["sub"]


def revoke_token(token: str) -> None:
    """Mark a token as revoked in Redis (TTL = 24 h)."""
    r = _get_redis()
    r.set(f"revoked:{token}", "1", ex=_REVOKE_TTL)
