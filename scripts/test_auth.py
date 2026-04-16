import urllib.request
import json
import urllib.error

def req(url, method="GET", data=None):
    print(f"\n--- {method} {url} ---")
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, data=data) as response:
            body = response.read().decode()
            print(json.dumps(json.loads(body), indent=2))
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}")
        print(json.dumps(json.loads(body), indent=2) if body else "")

req("http://localhost:8001/auth/register", "POST", {"hospital_id": "hospital-a", "password": "secret123"})
req("http://localhost:8001/auth/register", "POST", {"hospital_id": "hospital-a", "password": "anything"})
req("http://localhost:8001/auth/login", "POST", {"hospital_id": "hospital-a", "password": "secret123"})
req("http://localhost:8001/auth/public-key")
req("http://localhost:8001/health")
