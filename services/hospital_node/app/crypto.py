"""
crypto.py — AES weight encryption for secure federated learning.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
from the `cryptography` library for authenticated encryption
of serialized model weight bytes.

The same ENCRYPTION_KEY must be shared between hospital nodes
and the orchestrator via environment variable.
"""

import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")


def _get_fernet() -> Fernet:
    """Return a Fernet cipher using the configured encryption key."""
    if not _ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    return Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


def encrypt_weights(data: bytes) -> bytes:
    """Encrypt serialized weight bytes with AES.

    Args:
        data: Raw serialized weight bytes (e.g. from torch.save)

    Returns:
        Encrypted bytes (Fernet token)
    """
    f = _get_fernet()
    encrypted = f.encrypt(data)
    logger.debug("Encrypted %d bytes -> %d bytes", len(data), len(encrypted))
    return encrypted


def decrypt_weights(data: bytes) -> bytes:
    """Decrypt Fernet-encrypted weight bytes.

    Args:
        data: Encrypted bytes (Fernet token)

    Returns:
        Original serialized weight bytes
    """
    f = _get_fernet()
    decrypted = f.decrypt(data)
    logger.debug("Decrypted %d bytes -> %d bytes", len(data), len(decrypted))
    return decrypted
