# Tests and lint run in a Python 3.14 container, so nothing is installed on the host.
PYTHON_IMAGE ?= python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
VENV := .venv-docker
RUN := docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$(CURDIR)":/src -w /src $(PYTHON_IMAGE)

.PHONY: help
help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

$(VENV)/ready: requirements_test.txt
	$(RUN) sh -c 'python -m venv $(VENV) && $(VENV)/bin/pip install -q --disable-pip-version-check -r requirements_test.txt'
	touch $@

.PHONY: lint
lint: $(VENV)/ready ## Ruff lint and format check
	$(RUN) sh -c '$(VENV)/bin/ruff check . && $(VENV)/bin/ruff format --check .'

.PHONY: format
format: $(VENV)/ready ## Format with ruff
	$(RUN) sh -c '$(VENV)/bin/ruff check --fix . && $(VENV)/bin/ruff format .'

.PHONY: test
test: $(VENV)/ready ## Run the tests
	$(RUN) $(VENV)/bin/pytest -q

.PHONY: clean
clean: ## Remove the test environment and caches
	rm -rf $(VENV) .pytest_cache .ruff_cache
