"""
grpc_server.py — Orchestrator gRPC service handling model distribution and updates.

Handles:
  - GetGlobalModel: Sends encrypted global model to hospitals
  - SubmitUpdate: Receives encrypted weight deltas with metrics
  - Ping: Health check
"""

import io
import os
import sys
import asyncio
import logging

# Ensure proto stubs are importable regardless of Docker or local execution
_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import torch
import torch.nn as nn
import grpc

import fl_service_pb2 as pb2
import fl_service_pb2_grpc as pb2_grpc
from app.round_manager import RoundManager, RoundState
from app.crypto import encrypt_weights
from shared.auth_client import verify_grpc_token

logger = logging.getLogger(__name__)


def _init_model() -> dict:
    """Create a fresh MedModel CNN with random initial weights.

    Uses the same MedModel class as hospital nodes to ensure
    state_dict keys match (features.0.weight, features.3.weight, etc.).
    """
    from app.model import MedModel
    model = MedModel(n_classes=10)
    return model.state_dict()


class FLServicer(pb2_grpc.FLServiceServicer):
    """gRPC Service implementation for federated learning."""

    def __init__(self, manager: RoundManager):
        self.manager = manager

    async def GetGlobalModel(self, request, context):
        """Send the global model (encrypted) to a hospital node."""
        is_valid = await verify_grpc_token(request.token, request.hospital_id)
        if not is_valid:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            return

        # Provision a fresh global model if needed
        if self.manager.global_model is None:
            self.manager.global_model = _init_model()

        # Serialize
        buf = io.BytesIO()
        torch.save(self.manager.global_model, buf)
        raw_bytes = buf.getvalue()

        # Encrypt
        encrypted_bytes = encrypt_weights(raw_bytes)
        logger.info(
            "Sending encrypted global model to %s (%d -> %d bytes)",
            request.hospital_id, len(raw_bytes), len(encrypted_bytes),
        )

        algorithm = os.environ.get("AGGREGATION_ALGORITHM", "fedprox")
        mu = float(os.environ.get("FEDPROX_MU", "0.01"))

        return pb2.ModelResponse(
            weights=encrypted_bytes,
            round_id=self.manager.current_round,
            n_classes=10,
            encrypted=True,
            algorithm=algorithm,
            mu=mu,
        )

    async def SubmitUpdate(self, request, context):
        """Receive an encrypted weight update from a hospital."""
        is_valid = await verify_grpc_token(request.token, request.hospital_id)
        if not is_valid:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            return

        if self.manager.state != RoundState.WAITING:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "No active round")
            return

        if request.hospital_id not in self.manager.selected:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, "Not selected for this round")
            return

        logger.info(
            "Received update from %s: encrypted=%s acc=%.4f loss=%.4f",
            request.hospital_id, request.encrypted, request.accuracy, request.loss,
        )

        done = self.manager.record_update(
            hospital_id=request.hospital_id,
            weights_bytes=request.weight_delta,
            label_dist=list(request.label_dist),
            n_samples=request.n_samples,
            encrypted=request.encrypted,
            accuracy=request.accuracy,
            loss=request.loss,
        )

        # Trigger aggregation asynchronously if all updates arrived
        if done:
            asyncio.create_task(self.manager.aggregate_and_save())

        return pb2.UpdateAck(accepted=True, message="Update received")

    async def Ping(self, request, context):
        return pb2.PingResponse(status="alive")


async def serve(manager: RoundManager, port: int = 50051):
    """Start the asynchronous gRPC server."""
    server = grpc.aio.server()
    pb2_grpc.add_FLServiceServicer_to_server(FLServicer(manager), server)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info("gRPC server listening on port %d", port)
    await server.wait_for_termination()
