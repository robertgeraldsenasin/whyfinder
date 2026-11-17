import importlib

import pytest
from typer.testing import CliRunner

import whyfinder
from whyfinder.cli import app

SUBPACKAGES = ["data", "core", "graph", "rerank", "explain", "rag", "eval", "serve"]


def test_version_is_semver() -> None:
    parts = whyfinder.__version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackages_import_and_document_themselves(name: str) -> None:
    module = importlib.import_module(f"whyfinder.{name}")
    assert module.__doc__
    assert "Spec:" in module.__doc__


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == whyfinder.__version__


def test_cli_without_arguments_shows_help() -> None:
    result = CliRunner().invoke(app, [])
    assert "Whyfinder" in result.output
