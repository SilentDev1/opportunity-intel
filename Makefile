.PHONY: dev test lint typecheck migrate collect validate
dev:
	uv run uvicorn opportunity_intel.main:app --reload
test:
	uv run pytest
lint:
	uv run ruff check .
	uv run ruff format --check .
typecheck:
	uv run mypy src
migrate:
	uv run alembic upgrade head
collect:
	uv run opportunity-intel collect-all
validate:
	uv run opportunity-intel validate

