.PHONY: install lint format types imports test verify reproduce clean

install:
	uv sync --group dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

types:
	uv run mypy

imports:
	uv run lint-imports

test:
	uv run pytest --cov --cov-report=term

verify:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run lint-imports
	uv run pytest --cov --cov-report=term

reproduce:  ## from M1: rebuild every README number from raw data
	uv run dvc repro
	uv run python scripts/gen_readme_tables.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist
