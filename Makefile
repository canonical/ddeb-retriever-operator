ARCH := $(shell dpkg-architecture -q DEB_HOST_ARCH)
TARGET_CHARM := ddeb-retriever_$(ARCH).charm
TARGET_TEST_CHARM := ./ddeb-test/ddeb-test_$(ARCH).charm

.PHONY: all
all: build test

.PHONY: test
test:
	tox

.PHONY: integration-test
integration-test: build
	tox -e integration

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
		--config schedule=yearly
	uri=$$(juju add-secret lpsign 'config#file=./tests/integration/mock_lp_config.conf') && \
		juju grant-secret lpsign ddeb-retriever && \
		juju config ddeb-retriever "lp-sign-config=$${uri}"
	juju wait-for application ddeb-retriever

	juju deploy $(TARGET_TEST_CHARM)
	juju relate ddeb-retriever ddeb-test
	juju wait-for application ddeb-test

	# truncate the history for dev
	juju run ddeb-test/leader reset-timestamp
