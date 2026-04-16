from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

from .fedavg import b64_to_state_dict, state_dict_to_b64, fedavg
from .dwfed import dwfed
from .fedprox import fedprox_aggregate

app = FastAPI(title="MedFL Aggregation Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ClientUpdate(BaseModel):
    hospital_id: str
    label_dist: List[float]
    n_samples: int
    weights_b64: str

class AggregateRequest(BaseModel):
    round_id: int
    algorithm: str = "fedprox"
    global_dist: List[float] = []
    updates: List[ClientUpdate]

class AggregateResponse(BaseModel):
    round_id: int
    algorithm_used: str
    aggregated_weights: str
    ish_weights: Dict[str, float] = {}
    n_participants: int

@app.post("/aggregate", response_model=AggregateResponse)
def aggregate(req: AggregateRequest):
    if not req.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    parsed = []
    for u in req.updates:
        sd = b64_to_state_dict(u.weights_b64)
        parsed.append({
            "hospital_id": u.hospital_id,
            "state_dict": sd,
            "label_dist": u.label_dist,
            "n_samples": u.n_samples
        })
        
    if req.algorithm == "fedavg":
        aggregated_sd = fedavg(parsed)
        ish_weights = {}
    elif req.algorithm == "dwfed":
        if not req.global_dist:
            raise HTTPException(
                status_code=400,
                detail="global_dist is required for DWFed. "
                       "Orchestrator must compute and send it."
            )
        aggregated_sd, ish_weights = dwfed(parsed, req.global_dist)
    elif req.algorithm == "fedprox":
        if not req.global_dist:
            raise HTTPException(
                status_code=400,
                detail="global_dist is required for FedProx. "
                       "Orchestrator must compute and send it."
            )
        aggregated_sd, ish_weights = fedprox_aggregate(parsed, req.global_dist)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm: {req.algorithm}")
        
    weights_b64 = state_dict_to_b64(aggregated_sd)
    
    return AggregateResponse(
        round_id=req.round_id,
        algorithm_used=req.algorithm,
        aggregated_weights=weights_b64,
        ish_weights=ish_weights,
        n_participants=len(req.updates)
    )

@app.get("/algorithms")
def algorithms():
    return {
        "available": ["fedavg", "dwfed", "fedprox"],
        "default": "fedprox",
        "research_contribution": "dwfed",
        "recommended_non_iid": "fedprox",
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "aggregation"}
