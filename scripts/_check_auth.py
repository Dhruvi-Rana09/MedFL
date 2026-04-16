import ast
files = ["services/orchestrator/app/main.py", "services/orchestrator/app/grpc_server.py"]
for file in files:
    try:
        with open(file) as f:
            ast.parse(f.read())
        print(f"✓ {file} OK")
    except Exception as e:
        print(f"Error parsing {file}: {e}")
