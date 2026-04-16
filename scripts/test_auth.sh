# 1. Register hospital-a
echo "--- 1. Register hospital-a ---"
curl.exe -s -X POST http://localhost:8001/auth/register -H "Content-Type: application/json" -d "{\""hospital_id\"":\""hospital-a\"",\""password\"":\""secret123\""}"

echo -e "\n\n--- 2. Duplicate register must 409 ---"
curl.exe -s -X POST http://localhost:8001/auth/register -H "Content-Type: application/json" -d "{\""hospital_id\"":\""hospital-a\"",\""password\"":\""anything\""}"

echo -e "\n\n--- 3. Login ---"
curl.exe -s -X POST http://localhost:8001/auth/login -H "Content-Type: application/json" -d "{\""hospital_id\"":\""hospital-a\"",\""password\"":\""secret123\""}"

echo -e "\n\n--- 4. Public key endpoint ---"
curl.exe -s http://localhost:8001/auth/public-key

echo -e "\n\n--- 5. Health ---"
curl.exe -s http://localhost:8001/health
