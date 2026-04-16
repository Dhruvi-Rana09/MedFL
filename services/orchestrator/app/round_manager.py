"""
round_manager.py — Manages the lifecycle of federated learning training rounds.

Responsibilities:
  - Track round state (IDLE → WAITING → AGGREGATE → DONE)
  - Record encrypted hospital weight updates, decrypt them
  - Forward to aggregation service (FedAvg / DWFed / FedProx)
  - Evaluate global model accuracy on validation set
  - Save model to model-storage, push metrics to monitoring
"""

import os
import io
import json
import time
import base64
import logging
import traceback
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import torch
import torch.nn as nn
import httpx
from torch.utils.data import DataLoader

from app.crypto import decrypt_weights

logger = logging.getLogger(__name__)


class RoundState(Enum):
    IDLE = "idle"
    WAITING = "waiting"
    AGGREGATE = "aggregate"
    DONE = "done"


def _build_model(n_classes: int = 10) -> nn.Module:
    """Build a fresh MedModel instance for evaluation.

    Uses the same MedModel class as hospital nodes to ensure
    state_dict keys match (features.0.weight, features.3.weight, etc.).
    """
    from app.model import MedModel
    return MedModel(n_classes=n_classes)



@dataclass
class RoundManager:
    """Manages the lifecycle of a federated learning training round."""
    agg_url: str
    registry_url: str
    monitoring_url: str
    state: RoundState = RoundState.IDLE
    current_round: int = 0
    global_model: Optional[Dict[str, Any]] = None
    updates: List[Dict[str, Any]] = field(default_factory=list)
    selected: List[str] = field(default_factory=list)
    round_start_time: float = 0.0

    # Per-round metrics from hospitals
    hospital_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Full history of all rounds
    round_history: List[Dict[str, Any]] = field(default_factory=list)

    def start_round(self, hospital_ids: List[str]) -> None:
        """Initialize and start a new training round."""
        self.current_round += 1
        self.state = RoundState.WAITING
        self.selected = list(hospital_ids)
        self.updates.clear()
        self.hospital_metrics.clear()
        self.round_start_time = time.time()
        logger.info("[Round %d] Started. Waiting on %s", self.current_round, self.selected)

    def record_update(
        self,
        hospital_id: str,
        weights_bytes: bytes,
        label_dist: List[float],
        n_samples: int,
        encrypted: bool = False,
        accuracy: float = 0.0,
        loss: float = 0.0,
    ) -> bool:
        """Record an incoming weight update from a hospital.

        Returns True when all expected updates have arrived.
        """
        # Decrypt if encrypted
        raw_bytes = weights_bytes
        if encrypted:
            try:
                raw_bytes = decrypt_weights(weights_bytes)
                logger.info("[Round %d] Decrypted weights from %s", self.current_round, hospital_id)
            except Exception as e:
                logger.error("[Round %d] Failed to decrypt from %s: %s", self.current_round, hospital_id, e)
                return False

        buf = io.BytesIO(raw_bytes)
        try:
            state_dict = torch.load(buf, weights_only=False, map_location="cpu")
        except Exception as e:
            logger.error("[Round %d] Failed to load weights from %s: %s", self.current_round, hospital_id, e)
            return False

        self.updates.append({
            "hospital_id": hospital_id,
            "state_dict": state_dict,
            "label_dist": label_dist,
            "n_samples": n_samples,
        })

        # Store hospital-reported metrics
        self.hospital_metrics[hospital_id] = {
            "accuracy": accuracy,
            "loss": loss,
            "n_samples": n_samples,
        }

        logger.info(
            "[Round %d] Update from %s (%d/%d) acc=%.4f loss=%.4f",
            self.current_round, hospital_id,
            len(self.updates), len(self.selected),
            accuracy, loss,
        )

        return len(self.updates) >= len(self.selected)

    def compute_global_dist(self) -> List[float]:
        """Average all label distributions from the submitted updates."""
        if not self.updates:
            return []

        n_classes = len(self.updates[0].get("label_dist", []))
        if n_classes == 0:
            return []

        avg_dist = [0.0] * n_classes
        for u in self.updates:
            for i, val in enumerate(u.get("label_dist", [])):
                if i < n_classes:
                    avg_dist[i] += val

        return [v / len(self.updates) for v in avg_dist]

    def _compute_weighted_accuracy(self) -> tuple:
        """Compute sample-weighted average accuracy and loss from hospital reports."""
        if not self.hospital_metrics:
            return 0.0, 0.0

        total_samples = sum(m["n_samples"] for m in self.hospital_metrics.values())
        if total_samples == 0:
            return 0.0, 0.0

        weighted_acc = sum(
            m["accuracy"] * m["n_samples"] for m in self.hospital_metrics.values()
        ) / total_samples

        weighted_loss = sum(
            m["loss"] * m["n_samples"] for m in self.hospital_metrics.values()
        ) / total_samples

        return weighted_acc, weighted_loss

    async def aggregate_and_save(self) -> Dict[str, Any]:
        """Aggregate recorded updates, update global model, save metrics."""
        self.state = RoundState.AGGREGATE
        global_dist = self.compute_global_dist()
        duration_sec = time.time() - self.round_start_time

        algorithm = os.environ.get("AGGREGATION_ALGORITHM", "fedprox")

        # Build serialized update payloads
        serialized_updates = []
        for u in self.updates:
            buf = io.BytesIO()
            torch.save(u["state_dict"], buf)
            weights_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            serialized_updates.append({
                "hospital_id": u["hospital_id"],
                "label_dist": u["label_dist"],
                "n_samples": u["n_samples"],
                "weights_b64": weights_b64,
            })

        payload = {
            "round_id": self.current_round,
            "algorithm": algorithm,
            "global_dist": global_dist,
            "updates": serialized_updates,
        }

        # Dispatch to aggregation service
        agg_endpoint = f"{self.agg_url}/aggregate"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(agg_endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

        # Parse returned aggregated weights
        if "aggregated_weights" in result:
            agg_b64 = result["aggregated_weights"]
            agg_bytes = base64.b64decode(agg_b64)
            agg_buf = io.BytesIO(agg_bytes)
            self.global_model = torch.load(agg_buf, weights_only=False, map_location="cpu")

        # Compute weighted accuracy from hospital reports
        global_accuracy, global_loss = self._compute_weighted_accuracy()

        # Build round record
        round_record = {
            "round_id": self.current_round,
            "algorithm": algorithm,
            "accuracy": global_accuracy,
            "loss": global_loss,
            "duration_sec": round(duration_sec, 2),
            "participants": list(self.selected),
            "ish_weights": result.get("ish_weights", {}),
            "hospital_metrics": dict(self.hospital_metrics),
        }
        self.round_history.append(round_record)

        # Save and push metrics
        await self._save_to_registry(result, global_accuracy)
        await self._push_metrics(result, global_accuracy, global_loss, duration_sec)

        self.state = RoundState.DONE
        logger.info(
            "[Round %d] DONE — acc=%.4f loss=%.4f duration=%.1fs algo=%s",
            self.current_round, global_accuracy, global_loss, duration_sec, algorithm,
        )
        return round_record

    async def _save_to_registry(self, result: Dict[str, Any], accuracy: float) -> None:
        """Persist the global model and round metadata to model-storage."""
        try:
            model_storage_url = os.environ.get("MODEL_STORAGE_URL", "http://model-storage:8000")

            if self.global_model is not None:
                buf = io.BytesIO()
                torch.save(self.global_model, buf)
                buf.seek(0)
                model_bytes = buf.getvalue()

                metadata = {
                    "round_id": self.current_round,
                    "accuracy": accuracy,
                    "participants": self.selected,
                    "algorithm": os.environ.get("AGGREGATION_ALGORITHM", "fedprox"),
                    "ish_weights": result.get("ish_weights", {}),
                }

                files = {
                    "model_file": (f"model_{self.current_round}.pt", model_bytes, "application/octet-stream")
                }
                data = {
                    "round_id": str(self.current_round),
                    "metadata_json": json.dumps(metadata)
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(f"{model_storage_url}/models/upload", data=data, files=files)
                    resp.raise_for_status()

            logger.info("Saved round %d to model-storage (acc=%.4f)", self.current_round, accuracy)
        except Exception as e:
            logger.error("Failed to save round %d to registry: %s", self.current_round, e)
            logger.debug(traceback.format_exc())

    async def _push_metrics(
        self,
        result: Dict[str, Any],
        accuracy: float,
        loss: float,
        duration_sec: float,
    ) -> None:
        """Push round metrics to the monitoring service."""
        payload = {
            "round_id": self.current_round,
            "algorithm": os.environ.get("AGGREGATION_ALGORITHM", "fedprox"),
            "accuracy": accuracy,
            "loss": loss,
            "duration_sec": round(duration_sec, 2),
            "participants": list(self.selected),
            "ish_weights": result.get("ish_weights", {}),
            "hospital_metrics": dict(self.hospital_metrics),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{self.monitoring_url}/metrics/round", json=payload)
            logger.info("Pushed round %d metrics to monitoring", self.current_round)
        except Exception as e:
            logger.warning("Failed to push metrics to monitoring: %s", e)

    def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Recover the most recent global model from model-storage."""
        try:
            import requests
            model_storage_url = os.environ.get("MODEL_STORAGE_URL", "http://model-storage:8000")

            resp = requests.get(f"{model_storage_url}/models/latest", timeout=10.0)

            if resp.status_code == 204:
                return None

            resp.raise_for_status()

            buf = io.BytesIO(resp.content)
            return torch.load(buf, weights_only=False, map_location="cpu")

        except Exception as e:
            logger.warning("Failed to load latest checkpoint: %s", e)
            return None
