export LC_ALL=C

ifneq (,$(wildcard ./.env))
	include ./.env
	export
endif


help: ## Show the help.
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@fgrep "##" Makefile | fgrep -v fgrep

install: ## Install the packages.
	uv sync --all-packages

docker-build-backend: ## Build the backend Docker image.
	docker build -f applications/backend/Dockerfile -t jarvis-backend:latest .

docker-build-frontend: ## Build the frontend Docker image.
	docker build -f applications/frontend/Dockerfile -t jarvis-frontend:latest .

docker-build-assistant: ## Build the assistant Docker image.
	docker build -f applications/assistant/Dockerfile -t jarvis-assistant:latest .

docker-build-satellite: ## Build the satellite Docker image.
	docker build -f applications/satellite/Dockerfile -t jarvis-satellite:latest .

run-backend: ## Run the API application.
	PYTHONPATH=applications/backend/src uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

run-frontend: ## Run the Frontend application.
	PYTHONPATH=applications/frontend/src uv run streamlit run applications/frontend/src/frontend/app.py --server.port 8501

run-assistant: ## Run the Assistant application.
	PYTHONPATH=applications/assistant/src uv run uvicorn assistant.main:app --reload --host 0.0.0.0 --port 8001

run-satellite: ## Run the Satellite application.
	PYTHONPATH=applications/satellite/src uv run python applications/satellite/src/satellite/main.py

