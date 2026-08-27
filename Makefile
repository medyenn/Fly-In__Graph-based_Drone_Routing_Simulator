NAME		= fly_in
PYTHON		= python3
ENTRY		= src

all: run

install:
	@pip install -r requirements.txt

debug:
	@$(PYTHON) -m pdb $(ENTRY)

run:
	@$(PYTHON) $(ENTRY) $(ARGS)

clean:
	@rm -rf __pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@rm -rf .mypy_cache .pytest_cache .ruff_cache

re: clean install

lint:
	@flake8 src
	@mypy src --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs \
		--check-untyped-defs

docs:
	@echo "Open README.md"

help:
	@echo "Available targets:"
	@echo "  install      Install dependencies"
	@echo "  run          Run the project"
	@echo "  debug        Run the project under pdb"
	@echo "  clean        Remove Python/mypy/pytest caches"
	@echo "  re           clean + install"
	@echo "  lint         Run flake8 + mypy (mandatory flags)"

.PHONY: all install run debug clean re lint docs help
