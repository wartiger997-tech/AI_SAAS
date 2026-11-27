.PHONY: help up down logs ps migrate migrate-clause migrate-relay test lint fmt compose-config

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Start the full local stack (Postgres, Redis, MinIO, APIs, workers, web)
	docker compose -f infra/docker-compose.yml up -d --build

down: ## Stop the stack and remove volumes
	docker compose -f infra/docker-compose.yml down -v

logs: ## Tail all service logs
	docker compose -f infra/docker-compose.yml logs -f

ps: ## Show service status
	docker compose -f infra/docker-compose.yml ps

migrate: migrate-clause migrate-relay ## Run all migrations

migrate-clause: ## Run ClauseGuard migrations
	docker compose -f infra/docker-compose.yml exec clause-api alembic upgrade head

migrate-relay: ## Run Relay migrations
	docker compose -f infra/docker-compose.yml exec relay-api alembic upgrade head

test: ## Run all test suites
	cd apps/contract-redliner/api && python3.12 -m pytest
	cd apps/voice-receptionist/api && python3.12 -m pytest
	cd apps/voice-receptionist/agent && python3.12 -m pytest
	cd apps/contract-redliner/web && npm run typecheck

lint: ## Lint Python and web
	cd apps/contract-redliner/api && python3.12 -m ruff check src tests
	cd apps/voice-receptionist/api && python3.12 -m ruff check src tests
	cd apps/voice-receptionist/agent && python3.12 -m ruff check src tests
	cd apps/contract-redliner/web && npm run lint

fmt: ## Format Python
	cd apps/contract-redliner/api && python3.12 -m ruff format src tests
	cd apps/voice-receptionist/api && python3.12 -m ruff format src tests
	cd apps/voice-receptionist/agent && python3.12 -m ruff format src tests

compose-config: ## Validate compose syntax
	docker compose -f infra/docker-compose.yml config >/dev/null && echo "compose ok"