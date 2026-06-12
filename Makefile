.PHONY: all
all: lint test
	
.venv:
	uv sync --all-groups
	uv pip install -e .

.PHONY: lint
lint: .venv typecheck ruff format

.PHONY: typecheck
typecheck:
	uv run -m ty check

.PHONY: ruff
ruff:
	uv run -m ruff check

.PHONY: format
format:
	uv run -m ruff format --check --diff

.PHONY: test
test: .venv
	uv run -m pytest tests/unit

.PHONY: clean
clean:
	rm -rf .venv *.charm build
