"""
model_store.py — MinIO-backed model storage for global model weights.

Stores and retrieves serialised PyTorch state-dicts as binary blobs.
"""

import io
import logging
from typing import Optional

import torch
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


def _client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket() -> None:
    """Create the model bucket if it doesn't already exist."""
    client = _client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)
        logger.info("Created MinIO bucket: %s", settings.MINIO_BUCKET)


def save_model(state_dict: dict, round_id: int) -> str:
    """Serialise a state dict and upload to MinIO.

    Returns the object name used as the key.
    """
    buf = io.BytesIO()
    torch.save(state_dict, buf)
    buf.seek(0)
    length = buf.getbuffer().nbytes

    object_name = f"global_model_round_{round_id}.pt"
    client = _client()
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        buf,
        length,
        content_type="application/octet-stream",
    )
    logger.info("Saved model → %s/%s (%d bytes)", settings.MINIO_BUCKET, object_name, length)
    return object_name


def load_model(round_id: int) -> Optional[dict]:
    """Download and deserialise the global model for a given round.

    Returns None if the object doesn't exist.
    """
    object_name = f"global_model_round_{round_id}.pt"
    client = _client()

    try:
        response = client.get_object(settings.MINIO_BUCKET, object_name)
        buf = io.BytesIO(response.read())
        response.close()
        response.release_conn()
        return torch.load(buf, weights_only=False)
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            return None
        raise


def load_latest_model(current_round: int) -> Optional[dict]:
    """Walk backwards from current_round to find the most recent model."""
    for r in range(current_round, -1, -1):
        model = load_model(r)
        if model is not None:
            return model
    return None
