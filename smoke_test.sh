#!/bin/bash
# Full MedFL system smoke test
# Run from repo root after `make seed && make up`

echo "=== 1. Waiting for services to be healthy ==="
sleep 15

echo "=== 2. Health checks ==="
for port in 8000 8001 8002 8004; do
  resp=$(curl -s http://localhost:$port/health)
  echo "Port $port: $resp"
done

echo "=== 3. Hospital registrations (should auto-happen on startup) ==="
docker compose logs hospital-a | grep -i "registered\|token"
docker compose logs hospital-b | grep -i "registered\|token"
docker compose logs hospital-c | grep -i "registered\|token"

echo "=== 4. Trigger Round 1 (FedAvg baseline) ==="
curl -s -X POST http://localhost:8001/rounds/start \
  -H "Content-Type: application/json" \
  -d '{"hospital_ids":["hospital-a","hospital-b","hospital-c"],"algorithm":"fedavg"}'

echo "Waiting for round 1 to complete (watch logs in another terminal)..."
echo "Run: docker compose logs -f orchestrator"

# Poll until round is done
for i in $(seq 1 30); do
  state=$(curl -s http://localhost:8001/rounds/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['state'])" 2>/dev/null)
  echo "Round state: $state"
  [ "$state" = "idle" ] && [ "$i" -gt 1 ] && break
  sleep 10
done

echo "=== 5. Trigger Round 1 (DWFed) ==="
curl -s -X POST http://localhost:8001/rounds/start \
  -H "Content-Type: application/json" \
  -d '{"hospital_ids":["hospital-a","hospital-b","hospital-c"],"algorithm":"dwfed"}'

echo "=== 6. Check monitoring after rounds ==="
curl -s http://localhost:8004/metrics/history | python3 -m json.tool
curl -s http://localhost:8004/audit/log | python3 -m json.tool

echo "=== 7. Open these in your browser ==="
echo "Grafana:       http://localhost:3000  (admin / medfl)"
echo "MinIO Console: http://localhost:9001  (medfl / medfl-secret)"
echo "Auth API docs: http://localhost:8000/docs"
echo "Orchestrator:  http://localhost:8001/docs"
echo "Aggregation:   http://localhost:8002/docs"
echo "Monitoring:    http://localhost:8004/docs"

echo "=== Done! Run the comparison notebook: ==="
echo "jupyter notebook notebooks/dwfed_comparison.ipynb"
