Write-Host "Waiting for services to finish starting..."
Start-Sleep -Seconds 10

Write-Host "Triggering round 1 across hospital-a, hospital-b, hospital-c..."
$curlBody = '{"hospital_ids":["hospital-a","hospital-b","hospital-c"],"algorithm":"fedavg"}'
curl.exe -s -X POST http://localhost:8001/rounds/start -H "Content-Type: application/json" -d $curlBody | python -m json.tool

Start-Sleep -Seconds 3
Write-Host "`nChecking current round status..."
curl.exe -s http://localhost:8001/rounds/status | python -m json.tool

Write-Host "`nTo check the full logs of the orchestrator, you can manually run in your terminal:"
Write-Host "docker compose logs -f orchestrator"
