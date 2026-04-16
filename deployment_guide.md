# 🏥 MedFL Deployment & Testing Guide

This guide provides step-by-step instructions for running the MedFL Federated Learning platform on Windows.

## 1. Environment Preparation
Ensure Docker Desktop is running and you have Python installed.

```powershell
# Install required Python dependencies for local scripts
pip install torch torchvision grpcio grpcio-tools jupyter pandas matplotlib
```

## 2. Initialize the System
The system requires "seed data" to be present in the hospital volumes before startup.

```powershell
# Step A: Clean existing volumes (Optional)
docker compose down -v

# Step B: Generate local clinical datasets
python scripts/seed_data.py
```

## 3. Launch Services
Start the full microservice cluster:

```powershell
# Build and start in detached mode
docker compose up --build -d
```

## 4. Automatic Verification
Run the smoke test to verify all 8 services are healthy and communicating.

```powershell
.\smoke_test.ps1
```

## 5. Service Endpoints
| Service | URL | Purpose |
|---------|-----|---------|
| **Auth** | [http://localhost:8000/docs](http://localhost:8000/docs) | JWT Token Management |
| **Orchestrator** | [http://localhost:8001/docs](http://localhost:8001/docs) | Round Management (REST/gRPC) |
| **Aggregation** | [http://localhost:8002/docs](http://localhost:8002/docs) | FedAvg & DWFed Math Engine |
| **Monitoring** | [http://localhost:8004/docs](http://localhost:8004/docs) | Audit Logs & Prometheus |
| **Grafana** | [http://localhost:3000](http://localhost:3000) | Dashboard (admin/medfl) |
| **MinIO** | [http://localhost:9001](http://localhost:9001) | Model Storage (medfl/medfl-secret) |

## 6. Execution Workflow (Manual)
To manually trigger a training round via CLI:

```powershell
$body = '{"hospital_ids":["hospital-a","hospital-b","hospital-c"], "algorithm":"dwfed"}'
Invoke-RestMethod -Uri "http://localhost:8001/rounds/start" -Method Post -Body $body -ContentType "application/json"
```

## 7. Performance Analytics
Run the comparison notebook to see how **DWFed** improves model convergence over local unstructured data:
```powershell
jupyter notebook notebooks/dwfed_comparison.ipynb
```
