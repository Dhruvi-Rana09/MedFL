.PHONY: proto install-tools up down seed

install-tools:
	pip install grpcio grpcio-tools torch torchvision

proto:
	python -m grpc_tools.protoc \
	  -I./proto \
	  --python_out=./generated \
	  --grpc_python_out=./generated \
	  proto/fl_service.proto
	touch generated/__init__.py
	@echo "✓ Stubs generated in generated/"

seed:
	python scripts/seed_data.py

up:
	docker compose up --build

down:
	docker compose down -v
