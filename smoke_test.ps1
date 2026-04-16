Write-Host "=== 1. Waiting for services to be healthy ==="
Start-Sleep -Seconds 15

Write-Host "`n=== 2. Health checks ==="
foreach ($port in 8000, 8001, 8002, 8004) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:$port/health" -Method Get -ErrorAction Stop | ConvertTo-Json -Depth 1 -Compress
        Write-Host "Port ${port}: $resp"
    }
    catch {
        Write-Host "Port ${port}: Failed - $_"
    }
}

Write-Host "`n=== 3. Hospital registrations (should auto-happen on startup) ==="
docker compose logs hospital-a | Select-String -Pattern "registered|token"
docker compose logs hospital-b | Select-String -Pattern "registered|token"
docker compose logs hospital-c | Select-String -Pattern "registered|token"

Write-Host "`n=== 4. Trigger Round 1 (FedAvg baseline) ==="
$body1 = '{"hospital_ids":["hospital-a","hospital-b","hospital-c"],"algorithm":"fedavg"}'
Invoke-RestMethod -Uri http://localhost:8001/rounds/start -Method Post -Body $body1 -ContentType "application/json" | ConvertTo-Json

Write-Host "`nWaiting for round 1 to complete (watch logs in another terminal)..."
Write-Host "Run: docker compose logs -f orchestrator"

for ($i = 1; $i -le 30; $i++) {
    try {
        $stateObj = Invoke-RestMethod -Uri http://localhost:8001/rounds/status -Method Get -ErrorAction Stop
        $state = $stateObj.state
        Write-Host "Round state: $state"
        if ($state -eq "idle" -or $state -eq "done") {
            if ($i -gt 1) { break }
        }
    }
    catch {
        Write-Host "Polling error..."
    }
    Start-Sleep -Seconds 10
}

Write-Host "`n=== 5. Trigger Round 2 (DWFed) ==="
$body2 = '{"hospital_ids":["hospital-a","hospital-b","hospital-c"],"algorithm":"dwfed"}'
Invoke-RestMethod -Uri http://localhost:8001/rounds/start -Method Post -Body $body2 -ContentType "application/json" | ConvertTo-Json

# Give round 2 a moment to finish to populate metrics properly
Write-Host "`nWaiting for round 2 to complete..."
for ($i = 1; $i -le 30; $i++) {
    try {
        $stateObj = Invoke-RestMethod -Uri http://localhost:8001/rounds/status -Method Get -ErrorAction Stop
        $state = $stateObj.state
        Write-Host "Round state: $state"
        if ($state -eq "idle" -or $state -eq "done") {
            if ($i -gt 1) { break }
        }
    }
    catch {
        Write-Host "Polling error..."
    }
    Start-Sleep -Seconds 10
}

Write-Host "`n=== 6. Check monitoring after rounds ==="
Invoke-RestMethod -Uri http://localhost:8004/metrics/history -Method Get | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://localhost:8004/audit/log -Method Get | ConvertTo-Json -Depth 5

Write-Host "`n=== 7. Open these in your browser ==="
Write-Host "Grafana:       http://localhost:3000  (admin / medfl)"
Write-Host "MinIO Console: http://localhost:9001  (medfl / medfl-secret)"
Write-Host "Auth API docs: http://localhost:8000/docs"
Write-Host "Orchestrator:  http://localhost:8001/docs"
Write-Host "Aggregation:   http://localhost:8002/docs"
Write-Host "Monitoring:    http://localhost:8004/docs"

Write-Host "`n=== Done! Run the comparison notebook: ==="
Write-Host "jupyter notebook notebooks/dwfed_comparison.ipynb"
