"""
config.py — Orchestrator settings from environment variables.
"""

import os


class Settings:
    # ── Auth ─────────────────────────────────────────────────────────────
    AUTH_SERVICE_URL: str = os.environ.get("AUTH_SERVICE_URL", "http://auth:8000")

    # ── gRPC ─────────────────────────────────────────────────────────────
    GRPC_PORT: int = int(os.environ.get("GRPC_PORT", "50051"))

    # ── Federated Learning ───────────────────────────────────────────────
    FL_ROUNDS: int = int(os.environ.get("FL_ROUNDS", "10"))
    MIN_HOSPITALS: int = int(os.environ.get("MIN_HOSPITALS", "2"))

    # ── MinIO (model storage) ────────────────────────────────────────────
    MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.environ.get("MINIO_BUCKET", "medfl-models")
    MINIO_SECURE: bool = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    # ── Aggregation ──────────────────────────────────────────────────────
    AGGREGATION_URL: str = os.environ.get("AGGREGATION_URL", "http://aggregation:8000")

    # ── Monitoring ───────────────────────────────────────────────────────
    MONITORING_URL: str = os.environ.get("MONITORING_URL", "http://monitoring:8000")

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")


settings = Settings()
