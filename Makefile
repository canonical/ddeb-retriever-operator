.PHONY: all
all: lint test
	
.venv:
	uv sync --all-groups
	uv pip install -e .

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

.PHONY: test
test: .venv
	uv run pytest tests/unit

.PHONY: clean
clean:
	rm -rf .venv *.charm build
