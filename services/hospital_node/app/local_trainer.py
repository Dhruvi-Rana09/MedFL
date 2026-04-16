"""
local_trainer.py — Hospital-local training with FedProx proximal term + Differential Privacy.

Each federated round:
  1. Load global model weights from the orchestrator
  2. Train locally for N epochs with:
     - FedProx proximal term: (μ/2) * ||w - w_global||² added to loss
     - Optional Opacus differential privacy if DP_EPSILON < inf
  3. Compute and return weight delta, label distribution, accuracy, loss
"""

import os
import io
import pickle
import logging
import collections
from typing import Tuple, List, Dict, Any

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

from app.model import MedModel
from app.config import settings

logger = logging.getLogger(__name__)

N_CLASSES = settings.N_CLASSES
HOSPITAL_ID = settings.HOSPITAL_ID


def load_dataset() -> Dataset:
    """Load the pickled MNIST subset for this hospital."""
    with open(settings.DATA_PATH, "rb") as f:
        dataset = pickle.load(f)
    return dataset


def get_label_distribution(dataset) -> List[float]:
    """Return a 10-element frequency vector (one per class)."""
    labels = []
    for i in range(len(dataset)):
        _, label = dataset[i]
        labels.append(int(label))

    counts = collections.Counter(labels)
    total = len(labels)

    distribution = []
    for c in range(N_CLASSES):
        proportion = counts.get(c, 0) / total if total > 0 else 0.0
        distribution.append(float(proportion))

    return distribution


def _compute_delta(global_sd: dict, local_sd: dict) -> dict:
    """Compute (local - global) for every parameter."""
    delta = {}
    for key in global_sd:
        delta[key] = local_sd[key] - global_sd[key]
    return delta


def _state_dict_to_bytes(state_dict: dict) -> bytes:
    """Serialize a state dict to bytes."""
    buf = io.BytesIO()
    torch.save(state_dict, buf)
    return buf.getvalue()


def _bytes_to_state_dict(data: bytes) -> dict:
    """Deserialize bytes to a state dict."""
    buf = io.BytesIO(data)
    return torch.load(buf, weights_only=False, map_location="cpu")


def train_local(
    global_weights_bytes: bytes,
    mu: float = 0.01,
    algorithm: str = "fedprox",
) -> Dict[str, Any]:
    """Run local training and return results dict.

    Args:
        global_weights_bytes: Serialized global model state_dict (bytes).
                              If empty, initializes fresh model weights.
        mu: FedProx proximal term coefficient. Set to 0 for pure FedAvg.
        algorithm: Algorithm name ('fedprox', 'fedavg', 'dwfed').

    Returns:
        Dict with keys:
            - delta_bytes: serialized weight delta
            - label_dist: list of class frequencies
            - n_samples: number of training samples
            - accuracy: final test/train accuracy
            - loss: final average loss
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("[%s] Training on device: %s", HOSPITAL_ID, device)

    # 1. Build model
    model = MedModel(n_classes=N_CLASSES).to(device)

    # 2. Load global weights
    if global_weights_bytes and len(global_weights_bytes) > 0:
        global_sd = _bytes_to_state_dict(global_weights_bytes)
        model.load_state_dict(global_sd)
    else:
        global_sd = {k: v.clone() for k, v in model.state_dict().items()}

    # Snapshot for delta and FedProx proximal term
    global_snapshot = {k: v.clone().to(device) for k, v in model.state_dict().items()}

    # 3. Load dataset
    dataset = load_dataset()
    loader = DataLoader(
        dataset,
        batch_size=settings.BATCH_SIZE,
        shuffle=True,
        drop_last=True,
    )
    label_dist = get_label_distribution(dataset)
    n_samples = len(dataset)

    # 4. Optimizer and Loss
    optimizer = optim.SGD(
        model.parameters(),
        lr=settings.LEARNING_RATE,
        momentum=0.9,
    )
    criterion = nn.CrossEntropyLoss()

    # 5. Optional Differential Privacy with Opacus
    dp_enabled = settings.DP_EPSILON < float("inf")
    if dp_enabled:
        try:
            from opacus import PrivacyEngine
            privacy_engine = PrivacyEngine()
            model, optimizer, loader = privacy_engine.make_private_with_epsilon(
                module=model,
                optimizer=optimizer,
                data_loader=loader,
                epochs=settings.LOCAL_EPOCHS,
                target_epsilon=settings.DP_EPSILON,
                target_delta=settings.DP_DELTA,
                max_grad_norm=settings.DP_MAX_GRAD_NORM,
            )
            logger.info(
                "[%s] DP enabled: ε=%.2f δ=%s max_grad_norm=%.2f",
                HOSPITAL_ID, settings.DP_EPSILON, settings.DP_DELTA, settings.DP_MAX_GRAD_NORM,
            )
        except Exception as exc:
            logger.warning("[%s] Opacus DP failed, training without DP: %s", HOSPITAL_ID, exc)
            dp_enabled = False

    # Determine if FedProx proximal term should be used
    use_fedprox = algorithm in ("fedprox",) and mu > 0

    # 6. Training loop
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    for epoch in range(1, settings.LOCAL_EPOCHS + 1):
        epoch_loss = 0.0
        epoch_correct = 0
        epoch_samples = 0
        n_batches = 0

        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)

            # FedProx proximal term: (μ/2) * Σ||w_i - w_global_i||²
            if use_fedprox:
                proximal_term = 0.0
                # Get the right params depending on Opacus wrapping
                if dp_enabled and hasattr(model, "_module"):
                    local_params = model._module.named_parameters()
                else:
                    local_params = model.named_parameters()

                for name, param in local_params:
                    if name in global_snapshot:
                        proximal_term += ((param - global_snapshot[name]) ** 2).sum()

                loss = loss + (mu / 2.0) * proximal_term

            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

            # Compute accuracy
            _, predicted = torch.max(outputs.data, 1)
            epoch_correct += (predicted == labels).sum().item()
            epoch_samples += labels.size(0)

        avg_loss = epoch_loss / max(n_batches, 1)
        epoch_acc = epoch_correct / max(epoch_samples, 1)
        total_loss = avg_loss
        total_correct = epoch_correct
        total_samples = epoch_samples

        logger.info(
            "[%s] Epoch %d/%d  loss=%.4f  acc=%.4f",
            HOSPITAL_ID, epoch, settings.LOCAL_EPOCHS, avg_loss, epoch_acc,
        )

    # 7. Final accuracy
    final_accuracy = total_correct / max(total_samples, 1)
    final_loss = total_loss

    if dp_enabled:
        try:
            epsilon = privacy_engine.get_epsilon(delta=settings.DP_DELTA)
            logger.info("[%s] Training done. ε=%.2f, δ=%s", HOSPITAL_ID, epsilon, settings.DP_DELTA)
        except Exception:
            pass

    # 8. Get full updated weights (aggregation expects full state_dicts, not deltas)
    if dp_enabled and hasattr(model, "_module"):
        local_sd = model._module.state_dict()
    else:
        local_sd = model.state_dict()

    weights_bytes = _state_dict_to_bytes(local_sd)

    logger.info(
        "[%s] Training complete: %d samples, %d epochs, acc=%.4f, loss=%.4f, weights=%d bytes",
        HOSPITAL_ID, n_samples, settings.LOCAL_EPOCHS, final_accuracy, final_loss, len(weights_bytes),
    )

    return {
        "delta_bytes": weights_bytes,  # key kept for backward compatibility
        "label_dist": label_dist,
        "n_samples": n_samples,
        "accuracy": final_accuracy,
        "loss": final_loss,
    }
