"""
FedProx Aggregation — Proximal-term-aware weighted averaging for non-IID data.

Reference:
  "Federated Optimization in Heterogeneous Networks" (Li et al., MLSys 2020)

FedProx modifies training at the client-side by adding a proximal term
(μ/2) * ||w - w_global||² to prevent local models from diverging too far
from the global model. On the aggregation side, we combine:

  1. ISH-based weighting (from DWFed) to penalize statistically heterogeneous clients
  2. Sample-count weighting as a secondary factor

This gives us the best of both worlds: client-side drift prevention (FedProx)
and aggregation-side statistical awareness (DWFed ISH weighting).
"""

import numpy as np
from scipy.stats import wasserstein_distance


def compute_emd(local_dist: list, global_dist: list) -> float:
    """Compute the Earth Mover's Distance between local and global label distributions."""
    n_classes = len(local_dist)
    positions = np.arange(n_classes, dtype=float)
    return float(wasserstein_distance(
        positions,
        positions,
        np.array(local_dist),
        np.array(global_dist)
    ))


def compute_ish(emd: float) -> float:
    """Convert EMD into the Index of Statistical Heterogeneity."""
    return 1.0 / (1.0 + emd)


def fedprox_aggregate(updates: list, global_dist: list) -> tuple:
    """
    Aggregate state dictionaries using ISH-weighted averaging.

    The proximal regularization is enforced client-side during training.
    Aggregation simply uses the ISH-based dynamic weighting (same as DWFed)
    combined with sample counts for a balanced weighting scheme.

    Args:
        updates: list of dicts, each with:
            - "hospital_id": str
            - "state_dict": dict (PyTorch state_dict)
            - "label_dist": list[float]
            - "n_samples": int
        global_dist: list[float] — average label distribution across participants

    Returns:
        (aggregated_state_dict, weight_map)
    """
    # Compute ISH weights
    emds = []
    ishes = []
    for update in updates:
        emd = compute_emd(update["label_dist"], global_dist)
        emds.append(emd)
        ishes.append(compute_ish(emd))

    # Combine ISH with sample-count weighting
    total_samples = sum(u["n_samples"] for u in updates)
    sample_weights = [u["n_samples"] / total_samples for u in updates]

    # Hybrid weights: 70% ISH-based, 30% sample-count-based
    total_ish = sum(ishes)
    ish_weights = [ish / total_ish for ish in ishes]

    alpha = 0.7
    combined_weights = [
        alpha * iw + (1.0 - alpha) * sw
        for iw, sw in zip(ish_weights, sample_weights)
    ]

    # Normalize
    total_w = sum(combined_weights)
    weights = [w / total_w for w in combined_weights]

    hospital_info = {
        u["hospital_id"]: {
            "emd": round(emd, 4),
            "ish": round(ish, 4),
            "weight": round(w, 4)
        }
        for u, emd, ish, w in zip(updates, emds, ishes, weights)
    }

    print(f"[FedProx] Hospital weights: {hospital_info}")

    # Weighted aggregation of state dicts
    aggregated = {}
    first_sd = updates[0]["state_dict"]
    for key in first_sd.keys():
        aggregated[key] = sum(
            weights[i] * updates[i]["state_dict"][key].float()
            for i in range(len(updates))
        )

    weight_map = {u["hospital_id"]: round(w, 4) for u, w in zip(updates, weights)}
    return aggregated, weight_map
