def federated_averaging(updates: list[dict]) -> list[float]:
    """
    Weighted FedAvg — hospitals with more data have more influence
    """
    total_samples = sum(u["num_samples"] for u in updates)
    num_weights = len(updates[0]["weights"])

    averaged = []
    for i in range(num_weights):
        weighted_sum = sum(u["weights"][i] * u["num_samples"] for u in updates)
        averaged.append(weighted_sum / total_samples)

    return averaged


def is_malicious(weights: list[float], threshold: float = 10.0) -> bool:
    """
    Reject updates with extreme values (Byzantine fault detection)
    """
    return any(abs(w) > threshold for w in weights)