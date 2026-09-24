.PHONY: demo demo-stop test

TEST_POSTGRES_PORT ?= 55433

demo:
	./scripts/run_demo.sh

demo-stop:
	./scripts/stop_demo.sh

test:
	TEST_POSTGRES_PORT=$(TEST_POSTGRES_PORT) docker compose --profile test up -d --wait postgres-test
	cd backend && DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:$(TEST_POSTGRES_PORT)/immigration_flow_test uv run alembic upgrade head
	cd backend && TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:$(TEST_POSTGRES_PORT)/immigration_flow_test DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:$(TEST_POSTGRES_PORT)/immigration_flow_test uv run pytest -q
	cd backend && uv run ruff check app tests
	cd backend && uv run mypy app
	ruby scripts/validate_knowledge_base.rb
	npm --prefix apps/immigration-flow-web ci
	npm --prefix apps/immigration-flow-web run lint
	npm --prefix apps/immigration-flow-web run typecheck
	npm --prefix apps/immigration-flow-web test -- --run
	npm --prefix apps/immigration-flow-web run build
	npm --prefix apps/immigration-flow-web run e2e
