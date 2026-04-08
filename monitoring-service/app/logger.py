"""JSON-file-backed event logger."""

import json
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")


def _ensure_data_dir():
    """Create data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, "w") as f:
            json.dump([], f)


def _read_all() -> List[dict]:
    """Read all log records from disk."""
    _ensure_data_dir()
    try:
        with open(LOGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _write_all(records: List[dict]):
    """Write all log records to disk."""
    _ensure_data_dir()
    with open(LOGS_FILE, "w") as f:
        json.dump(records, f, indent=2)


def add_log(event: str, source: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> dict:
    """Append a new log entry with auto-generated timestamp and ID."""
    records = _read_all()

    new_id = max((r.get("id", 0) for r in records), default=0) + 1

    record = {
        "id": new_id,
        "event": event,
        "source": source,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    records.append(record)
    _write_all(records)
    return record


def get_logs(limit: Optional[int] = None, source: Optional[str] = None) -> List[dict]:
    """Retrieve logs, optionally filtered by source and limited in count."""
    records = _read_all()

    # Filter by source if specified
    if source:
        records = [r for r in records if r.get("source") == source]

    # Sort newest first
    records = sorted(records, key=lambda r: r.get("id", 0), reverse=True)

    # Apply limit
    if limit is not None and limit > 0:
        records = records[:limit]

    return records
