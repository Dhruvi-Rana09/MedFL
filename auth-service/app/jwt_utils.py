from jose import jwt, JWTError
from datetime import datetime, timedelta
import os, redis as redis_lib

# Load keys from disk (path can be overridden via environment variable)
PRIVATE_KEY = open(os.environ.get("JWT_PRIVATE_KEY_PATH", "/app/certs/private.pem")).read()
PUBLIC_KEY  = open(os.environ.get("JWT_PUBLIC_KEY_PATH", "/app/certs/public.pem")).read()
ALGORITHM   = "RS256"  # asymmetric: sign with private, verify with public
EXPIRE_MINS = 60 * 24  # token valid for 24 hours

# Connect to Redis — URL comes from environment variable
r = redis_lib.from_url(os.environ["REDIS_URL"])

def create_token(hospital_id: str) -> str:
    """Create a signed JWT for a hospital."""
    payload = {
        "sub": hospital_id,                                     # "subject" = who this is for
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRE_MINS), # expiry time
        "iat": datetime.utcnow(),                                # issued at
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> str:
    """Verify token is valid and not revoked. Returns hospital_id."""
    # Step 1: check revocation list in Redis
    if r.get(f"revoked:{token}"):
        raise ValueError("Token has been revoked")
    
    # Step 2: decode and verify signature + expiry
    # This raises JWTError automatically if invalid or expired
    payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
    
    return payload["sub"]  # return the hospital_id

def revoke_token(token: str) -> None:
    """Add token to blocklist — it will auto-expire after 24h."""
    r.setex(f"revoked:{token}", EXPIRE_MINS * 60, "1")