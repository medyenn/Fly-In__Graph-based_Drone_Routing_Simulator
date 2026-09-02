NAME = fly_in
PYTHON = python3
ENTRY = src

all: run

install:
	@$(PYTHON) -m pip install -r requirements.txt

run:
	@$(PYTHON) $(ENTRY) $(ARGS)

visual:
	@$(PYTHON) $(ENTRY) $(ARGS) --visual

debug:
	@$(PYTHON) -m pdb $(ENTRY) $(ARGS)

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@rm -rf .mypy_cache .pytest_cache .ruff_cache .venv uv.lock
	@rm -rf */*arcade*

lint:
	@flake8 .
	@mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs \
		--check-untyped-defs

lint-strict:
	@flake8 .
	@mypy . --strict

.PHONY: all install run gui debug clean lint lint-strict
