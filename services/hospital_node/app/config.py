"""
config.py — Hospital Node settings from environment variables.
"""

import os


class Settings:
    # ── Identity ─────────────────────────────────────────────────────────
    HOSPITAL_ID: str = os.environ.get("HOSPITAL_ID", "hospital_a")
    HOSPITAL_PASSWORD: str = os.environ.get("HOSPITAL_PASSWORD", "changeme")

    # ── Data ─────────────────────────────────────────────────────────────
    DATA_PATH: str = os.environ.get("DATA_PATH", "/data/dataset.pkl")

    # ── Training hyperparameters ─────────────────────────────────────────
    LOCAL_EPOCHS: int = int(os.environ.get("LOCAL_EPOCHS", "3"))
    BATCH_SIZE: int = int(os.environ.get("BATCH_SIZE", "32"))
    LEARNING_RATE: float = float(os.environ.get("LEARNING_RATE", "0.01"))

    # ── Differential Privacy (Opacus) ────────────────────────────────────
    DP_EPSILON: float = float(os.environ.get("DP_EPSILON", "1.0"))
    DP_DELTA: float = float(os.environ.get("DP_DELTA", "1e-5"))
    DP_MAX_GRAD_NORM: float = float(os.environ.get("DP_MAX_GRAD_NORM", "1.0"))

    # ── FedProx ──────────────────────────────────────────────────────────
    FEDPROX_MU: float = float(os.environ.get("FEDPROX_MU", "0.01"))

    # ── Security ─────────────────────────────────────────────────────────
    ENCRYPTION_KEY: str = os.environ.get("ENCRYPTION_KEY", "")

    # ── Services ─────────────────────────────────────────────────────────
    AUTH_SERVICE_URL: str = os.environ.get("AUTH_URL", "http://auth:8000")
    ORCHESTRATOR_URL: str = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000")
    ORCHESTRATOR_GRPC: str = os.environ.get("ORCHESTRATOR_GRPC", "orchestrator:50051")

    # ── Number of classes ────────────────────────────────────────────────
    N_CLASSES: int = int(os.environ.get("N_CLASSES", "10"))


settings = Settings()
