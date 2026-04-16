"""
DWFed Algorithm Implementation.

Reference: "DWFed: A statistical-heterogeneity-based dynamic weighted model aggregation algorithm for federated learning" 
(Frontiers in Neurorobotics, 2022).

Standard Federated Averaging (FedAvg) aggregates hospital models by uniformly weighting them based on dataset sizes. 
However, on non-IID (Independent and Identically Distributed) data, FedAvg becomes vulnerable; hospitals with heavy 
class imbalances can skew the global model and drastically hurt model convergence.

DWFed solves this by dynamically identifying the "Statistical Heterogeneity" of each hospital. It compares each 
hospital's local label distribution against the global label distribution using the Earth Mover's Distance (EMD), 
or Wasserstein-1 distance. 

Using the EMD, it computes an Index of Statistical Heterogeneity (ISH) using the formula:
    ISH = 1.0 / (1.0 + EMD)

The lower the EMD (more globally representative data distribution), the higher the ISH (approaching 1.0). 
Hospitals are then weighted proportionally to their relative ISH, prioritizing representative datasets and 
suppressing statistical outliers during global aggregation.
"""

import numpy as np
from scipy.stats import wasserstein_distance

def compute_emd(local_dist: list[float], global_dist: list[float]) -> float:
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

def dwfed(updates: list[dict], global_dist: list[float]) -> tuple[dict, dict]:
    """
    Aggregate state dictionaries using the ISH-derived dynamic weights.
    
    Args:
        updates: list of dicts, each with:
            - "hospital_id": str
            - "state_dict": dict (PyTorch state_dict)
            - "label_dist": list[float]
            - "n_samples": int
        global_dist: list[float] — average label distribution across all participants
    
    Returns:
        (aggregated_state_dict, ish_map)
    """
    emds = []
    ishes = []
    
    for update in updates:
        emd = compute_emd(update["label_dist"], global_dist)
        emds.append(emd)
        ishes.append(compute_ish(emd))
        
    total_ish = sum(ishes)
    weights = [ish / total_ish for ish in ishes]
    
    hospital_emds = {u["hospital_id"]: round(emd, 4) for u, emd in zip(updates, emds)}
    hospital_ishes = {u["hospital_id"]: round(ish, 4) for u, ish in zip(updates, ishes)}
    hospital_weights = {u["hospital_id"]: round(weight, 4) for u, weight in zip(updates, weights)}
    
    print(f"[DWFed] Hospital EMDs: {hospital_emds}")
    print(f"[DWFed] ISH values: {hospital_ishes}")
    print(f"[DWFed] Final weights: {hospital_weights}")
    
    aggregated = {}
    first_sd = updates[0]["state_dict"]
    
    for key in first_sd.keys():
        aggregated[key] = sum(
            weights[i] * updates[i]["state_dict"][key].float()
            for i in range(len(updates))
        )
        
    return aggregated, hospital_weights
