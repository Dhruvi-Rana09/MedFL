import ast, sys, pathlib

files = [
    # Orchestrator
    "services/orchestrator/app/config.py",
    "services/orchestrator/app/auth.py",
    "services/orchestrator/app/model_store.py",
    "services/orchestrator/app/round_manager.py",
    "services/orchestrator/app/grpc_server.py",
    "services/orchestrator/app/main.py",
    # Hospital Node
    "services/hospital_node/app/config.py",
    "services/hospital_node/app/model.py",
    "services/hospital_node/app/train.py",
    "services/hospital_node/app/main.py",
    # Aggregation
    "services/aggregation/app/fedavg.py",
    "services/aggregation/app/main.py",
    # Monitoring
    "services/monitoring/app/main.py",
]

ok = 0
for f in files:
    try:
        with open(f) as fh:
            ast.parse(fh.read())
        print(f"  ✓ {f}")
        ok += 1
    except SyntaxError as e:
        print(f"  ✗ {f}: {e}")

print(f"\n{ok}/{len(files)} files OK")
