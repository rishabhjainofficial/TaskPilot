.PHONY: help dev down test migrate seed lint

help:
	@echo "Available commands:"
	@echo "  make dev      - Start all services with docker compose"
	@echo "  make down     - Stop all containers"
	@echo "  make migrate  - Run database migrations"
	@echo "  make seed     - Seed default roles, permissions, and plans"
	@echo "  make test     - Run pytest suite in backend"

dev:
	docker compose up --build

down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python3 -m seeds.seed_roles_permissions && python3 -m seeds.seed_plans

test:
	cd backend && pytest -v
