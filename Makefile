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

.PHONY: build
build:
	charmcraft pack
	env -C ./ddeb-test charmcraft pack
.PHONY: dev-deploy
dev-deploy:
	juju deploy ./ddeb-retriever_amd64.charm --config schedule=yearly
	juju deploy ./ddeb-test/ddeb-test_amd64.charm
	juju relate ddeb-retriever ddeb-test

	# wait for charms to settle
	juju exec --parallel=false --all true

	uri=$$(juju add-secret lpsign 'config#file=./tests/integration/mock_lp_config.conf') && \
		juju grant-secret lpsign ddeb-retriever && \
		juju config ddeb-retriever "lp-sign-config=$${uri}"

	# wait for charms to settle again
	juju exec --parallel=false --all true

	# truncate the history for dev
	juju run ddeb-test/leader reset-timestamp

