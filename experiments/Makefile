.DEFAULT_GOAL := help

# source: https://stackoverflow.com/questions/18136918/how-to-get-current-relative-directory-of-your-makefile#73509979
MAKEFILE_ABS_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
RUFF_CONFIG_FILE := $(realpath $(MAKEFILE_ABS_DIR)/../utilities/ruff.toml)
MYPY_CONFIG_FILE := $(realpath $(MAKEFILE_ABS_DIR)/../utilities/mypy.ini)

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([0-9a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

.PHONY: format
format: ## format code base via "ruff format"
	ruff --config=$(RUFF_CONFIG_FILE) format $(MAKEFILE_ABS_DIR)

.PHONY: format-check
format-check: ## check code formatting via "ruff format"
	ruff --config=$(RUFF_CONFIG_FILE) format --check $(MAKEFILE_ABS_DIR)

.PHONY: help
help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

.PHONY: lint
lint: ruff format ## apply linting and code formatting

.PHONY: lint-check
lint-check: ruff-check format-check ## check linting and code formatting

.PHONY: mypy-nbqa
mypy-nbqa: ## static check with mypy on jupyter notebooks via nbqa
	nbqa mypy --config-file=$(MYPY_CONFIG_FILE) $(MAKEFILE_ABS_DIR)

.PHONY: ruff
ruff: ## run ruff linter on the project. Act on fixable issues
	ruff --config=$(RUFF_CONFIG_FILE) check --fix $(MAKEFILE_ABS_DIR)

.PHONY: ruff-check
ruff-check: ## run ruff linter on the project, do not change files
	ruff --config=$(RUFF_CONFIG_FILE) check $(MAKEFILE_ABS_DIR)
