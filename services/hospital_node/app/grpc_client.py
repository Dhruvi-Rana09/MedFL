"""
grpc_client.py — Hospital node gRPC client for federated learning rounds.

Handles:
  1. Fetching the encrypted global model from the orchestrator
  2. Decrypting, training locally (FedProx + DP), encrypting weight delta
  3. Submitting encrypted update with accuracy/loss metrics
"""

import os
import sys
import logging

# Ensure proto stubs are importable regardless of Docker or local execution
_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import grpc

from app.local_trainer import train_local
from app.crypto import encrypt_weights, decrypt_weights
from app.config import settings

import fl_service_pb2 as pb2
import fl_service_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)

HOSPITAL_ID = settings.HOSPITAL_ID
ORCHESTRATOR_GRPC = settings.ORCHESTRATOR_GRPC


async def participate_in_round(token: str) -> dict:
    """Execute one full federated learning round.

    1. Get encrypted global model from orchestrator
    2. Decrypt and train locally
    3. Encrypt weight delta and submit with metrics

    Returns:
        Dict with round_id, n_samples, label_dist, accuracy, loss
    """
    try:
        async with grpc.aio.insecure_channel(ORCHESTRATOR_GRPC) as channel:
            stub = pb2_grpc.FLServiceStub(channel)

            # ── Step 1: Get Global Model ────────────────────────────────
            request = pb2.ModelRequest(hospital_id=HOSPITAL_ID, token=token)
            response = await stub.GetGlobalModel(request)

            # Decrypt if encrypted
            raw_weights = response.weights
            if response.encrypted:
                logger.info("[%s] Decrypting global model weights...", HOSPITAL_ID)
                raw_weights = decrypt_weights(raw_weights)

            # Get algorithm and mu from server response
            algorithm = response.algorithm or "fedprox"
            mu = response.mu if response.mu > 0 else settings.FEDPROX_MU

            logger.info(
                "[%s] Received round %d model (algo=%s, mu=%.3f)",
                HOSPITAL_ID, response.round_id, algorithm, mu,
            )

            # ── Step 2: Local Training ──────────────────────────────────
            result = train_local(
                global_weights_bytes=raw_weights,
                mu=mu,
                algorithm=algorithm,
            )

            delta_bytes = result["delta_bytes"]
            label_dist = result["label_dist"]
            n_samples = result["n_samples"]
            accuracy = result["accuracy"]
            loss = result["loss"]

            # ── Step 3: Encrypt and Submit ──────────────────────────────
            encrypted_delta = encrypt_weights(delta_bytes)
            logger.info(
                "[%s] Encrypting weight delta: %d -> %d bytes",
                HOSPITAL_ID, len(delta_bytes), len(encrypted_delta),
            )

            update_req = pb2.UpdateRequest(
                hospital_id=HOSPITAL_ID,
                token=token,
                round_id=response.round_id,
                weight_delta=encrypted_delta,
                label_dist=label_dist,
                n_samples=n_samples,
                encrypted=True,
                accuracy=accuracy,
                loss=loss,
            )
            ack = await stub.SubmitUpdate(update_req)

            logger.info("[%s] Submitted update: %s", HOSPITAL_ID, ack.message)

            return {
                "round_id": response.round_id,
                "n_samples": n_samples,
                "label_dist": label_dist,
                "accuracy": accuracy,
                "loss": loss,
            }

    except grpc.RpcError as e:
        logger.error("[%s] gRPC Error: %s - %s", HOSPITAL_ID, e.code(), e.details())
        raise
