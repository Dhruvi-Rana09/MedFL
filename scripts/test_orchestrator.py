import sys
import os
import urllib.request
import json
import urllib.error
import grpc

# Add the 'generated' directory to the path so grpc can import stubs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))
import fl_service_pb2 as pb2
import fl_service_pb2_grpc as pb2_grpc

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

# 1. Health check
req("http://localhost:8002/health")

# 2. Check round status
req("http://localhost:8002/rounds/status")

# 3. Ping gRPC server
print("\n--- gRPC Ping ---")
try:
    with grpc.insecure_channel('localhost:50051') as ch:
        stub = pb2_grpc.FLServiceStub(ch)
        resp = stub.Ping(pb2.PingRequest(hospital_id='test'))
        print('gRPC Ping:', resp.status)
except Exception as e:
    print(f"gRPC Ping Failed: {e}")
