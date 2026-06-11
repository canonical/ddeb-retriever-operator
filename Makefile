.venv:
	uv venv
	uv pip install -e .[lint]

.PHONY: lint
lint: .venv typecheck ruff format

.PHONY: typecheck
typecheck:
	uv run ty check

.PHONY: ruff
ruff:
	uv run ruff check

.PHONY: format
format:
	uv run ruff format --check --diff
