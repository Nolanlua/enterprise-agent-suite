SHELL := /bin/bash
.PHONY: bootstrap infra-up infra-down data dev lint test fmt

bootstrap:
	uv sync --all-packages

infra-up:
	docker compose -f deploy/docker-compose.yml up -d postgres redis qdrant opensearch minio

infra-down:
	docker compose -f deploy/docker-compose.yml down -v

data:
	uv run python platforms/data-platform/simulators/generate_tcm.py
	uv run python platforms/data-platform/simulators/generate_retail.py

dev:
	@echo "Run each service in a separate terminal:"
	@echo "  cd platforms/data-platform && uv run uvicorn app.main:app --port 8001"
	@echo "  cd platforms/eval-platform && uv run uvicorn app.main:app --port 8002"
	@echo "  cd apps/tcm-knowledge-agent && uv run uvicorn app.main:app --port 8011"
	@echo "  cd apps/retail-ordering-agent && uv run uvicorn app.main:app --port 8012"

lint:
	uv run ruff check .
	uv run mypy packages platforms apps

test:
	uv run pytest

fmt:
	uv run ruff format .