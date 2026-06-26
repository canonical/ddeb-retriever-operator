ARCH := $(shell dpkg-architecture -q DEB_HOST_ARCH)
TARGET_CHARM := ddeb-retriever_$(ARCH).charm
TARGET_TEST_CHARM := ./ddeb-test/ddeb-test_$(ARCH).charm

.PHONY: all
all: lint test
	
.PHONY: .venv
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

.PHONY: integration-test
integration-test: build
	uv run -m pytest -v tests/integration

.PHONY: clean
clean:
	rm -rf .venv *.charm build

.PHONY: build
build: $(TARGET_CHARM) $(TARGET_TEST_CHARM)

$(TARGET_CHARM): charmcraft.yaml $(wildcard src/*.py)
	charmcraft pack
$(TARGET_TEST_CHARM): ddeb-test/charmcraft.yaml $(wildcard ddeb-test/src/*.py)
	env -C ./ddeb-test charmcraft pack

.PHONY: dev-deploy
dev-deploy: build
	juju deploy ./ddeb-retriever_amd64.charm \
		--config schedule=yearly \
		--config git-repository=https://git.launchpad.net/~simpoir/ddeb-retriever/+git/ddeb-retriever \
		--config git-ref=lpsign
	juju deploy $(TARGET_TEST_CHARM)
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
