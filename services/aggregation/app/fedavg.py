import io
import base64
import torch

def b64_to_state_dict(b64: str) -> dict:
    b = base64.b64decode(b64)
    try:
        return torch.load(io.BytesIO(b), weights_only=True)
    except TypeError:
        return torch.load(io.BytesIO(b))

def state_dict_to_b64(state_dict: dict) -> str:
    buf = io.BytesIO()
    torch.save(state_dict, buf)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def fedavg(updates: list[dict]) -> dict:
    total = sum(u["n_samples"] for u in updates)
    
    weights = [u["n_samples"] / total for u in updates]
    
    weight_dict = {u["hospital_id"]: round(w, 3) for u, w in zip(updates, weights)}
    print(f"[FedAvg] Weights: {weight_dict}")
    
    aggregated = {}
    first_sd = updates[0]["state_dict"]
    
    for key in first_sd.keys():
        aggregated[key] = sum(
            w * u["state_dict"][key].float() 
            for w, u in zip(weights, updates)
        )
        
    return aggregated
