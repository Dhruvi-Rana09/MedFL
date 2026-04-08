"""Automated tests for the Monitoring Service API."""

import sys
import os
import json
import pytest

# The Dockerfile copies app/ contents into /app, so at runtime `main.py`
# imports `logger` and `schemas` as top-level modules.  We replicate that
# here by putting the app/ directory on sys.path.
APP_DIR = os.path.join(os.path.dirname(__file__), "app")
sys.path.insert(0, APP_DIR)

from fastapi.testclient import TestClient  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_data(tmp_path, monkeypatch):
    """Redirect the JSON data file to a temp directory so tests are isolated."""
    import logger  # imported after sys.path adjustment

    monkeypatch.setattr(logger, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(logger, "LOGS_FILE", str(tmp_path / "logs.json"))


@pytest.fixture()
def client():
    """Provide a fresh TestClient for each test."""
    from main import app  # imported after sys.path adjustment
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests — Health Check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_root_returns_running(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "monitoring"
        assert data["status"] == "running"


# ---------------------------------------------------------------------------
# Tests — POST /log
# ---------------------------------------------------------------------------

class TestCreateLog:
    def test_create_log_full(self, client):
        """POST /log with all fields."""
        payload = {
            "event": "training_started",
            "source": "hospital_1",
            "details": {"epoch": 1, "lr": 0.01},
        }
        resp = client.post("/log", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "logged"
        assert isinstance(data["id"], int)
        assert data["id"] >= 1

    def test_create_log_minimal(self, client):
        """POST /log with only the required `event` field."""
        resp = client.post("/log", json={"event": "ping"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "logged"
        assert data["id"] >= 1

    def test_create_log_missing_event(self, client):
        """POST /log without the required `event` should be 422."""
        resp = client.post("/log", json={"source": "test"})
        assert resp.status_code == 422

    def test_create_multiple_logs_increment_id(self, client):
        """Each log should get a higher ID."""
        r1 = client.post("/log", json={"event": "a"}).json()
        r2 = client.post("/log", json={"event": "b"}).json()
        r3 = client.post("/log", json={"event": "c"}).json()
        assert r1["id"] < r2["id"] < r3["id"]


# ---------------------------------------------------------------------------
# Tests — GET /logs
# ---------------------------------------------------------------------------

class TestGetLogs:
    def _seed(self, client, n=5):
        """Insert n log entries and return their IDs."""
        ids = []
        for i in range(n):
            resp = client.post("/log", json={
                "event": f"event_{i}",
                "source": "src_a" if i % 2 == 0 else "src_b",
            })
            ids.append(resp.json()["id"])
        return ids

    def test_get_logs_empty(self, client):
        resp = client.get("/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_logs_returns_all(self, client):
        self._seed(client, 5)
        resp = client.get("/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 5

    def test_get_logs_newest_first(self, client):
        self._seed(client, 5)
        logs = client.get("/logs").json()
        ids = [l["id"] for l in logs]
        assert ids == sorted(ids, reverse=True), "Logs should be newest-first"

    def test_get_logs_limit(self, client):
        self._seed(client, 5)
        logs = client.get("/logs", params={"limit": 2}).json()
        assert len(logs) == 2

    def test_get_logs_filter_source(self, client):
        self._seed(client, 6)
        logs = client.get("/logs", params={"source": "src_a"}).json()
        assert all(l["source"] == "src_a" for l in logs)
        assert len(logs) == 3  # indices 0, 2, 4

    def test_get_logs_filter_source_and_limit(self, client):
        self._seed(client, 6)
        logs = client.get("/logs", params={"source": "src_a", "limit": 1}).json()
        assert len(logs) == 1
        assert logs[0]["source"] == "src_a"

    def test_log_record_has_expected_fields(self, client):
        client.post("/log", json={"event": "test", "source": "s", "details": {"k": 1}})
        logs = client.get("/logs").json()
        record = logs[0]
        assert "id" in record
        assert "event" in record
        assert "source" in record
        assert "details" in record
        assert "timestamp" in record
        assert record["event"] == "test"
        assert record["details"] == {"k": 1}
