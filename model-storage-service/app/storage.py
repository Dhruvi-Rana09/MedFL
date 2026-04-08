"""JSON-file-backed model storage logic."""

import json
import os
from datetime import datetime, timezone
from typing import Optional, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MODELS_FILE = os.path.join(DATA_DIR, "models.json")


def _ensure_data_dir():
    """Create data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(MODELS_FILE):
        with open(MODELS_FILE, "w") as f:
            json.dump([], f)


def _read_all() -> List[dict]:
    """Read all model records from disk."""
    _ensure_data_dir()
    try:
        with open(MODELS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _write_all(records: List[dict]):
    """Write all model records to disk."""
    _ensure_data_dir()
    with open(MODELS_FILE, "w") as f:
        json.dump(records, f, indent=2)


def save_model(round_number: int, weights: List[float], accuracy: Optional[float] = None) -> dict:
    """Save a model snapshot after an aggregation round."""
    records = _read_all()

    record = {
        "round_number": round_number,
        "weights": weights,
        "accuracy": accuracy,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Overwrite if same round exists, otherwise append
    existing_idx = next((i for i, r in enumerate(records) if r["round_number"] == round_number), None)
    if existing_idx is not None:
        records[existing_idx] = record
    else:
        records.append(record)

    _write_all(records)
    return record


def load_latest() -> Optional[dict]:
    """Return the most recent model record."""
    records = _read_all()
    if not records:
        return None
    return max(records, key=lambda r: r["round_number"])


def load_by_round(round_number: int) -> Optional[dict]:
    """Return a specific round's model record."""
    records = _read_all()
    for r in records:
        if r["round_number"] == round_number:
            return r
    return None


def load_all() -> List[dict]:
    """Return entire model history."""
    records = _read_all()
    return sorted(records, key=lambda r: r["round_number"])
