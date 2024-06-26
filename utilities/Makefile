.DEFAULT_GOAL := help

# source: https://stackoverflow.com/questions/18136918/how-to-get-current-relative-directory-of-your-makefile#73509979
MAKEFILE_ABS_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([0-9a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

.PHONY: black
black: ## apply black formatting
	black .

.PHONY: black-check
black-check: ## check black formatting
	black --check .

.PHONY: help
help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

.PHONY: lint
lint: ruff black ## apply linting and black formatting

.PHONY: lint-check
lint-check: ruff-check black-check ## check linting and black formatting

.PHONY: mypy
mypy: ## static check with mypy
	mypy .

.PHONY: ruff
ruff: ## run ruff linter on the project. Act on fixable issues
	ruff check --fix .

.PHONY: ruff-check
ruff-check: ## run ruff linter on the project, do not change files
	ruff check .
