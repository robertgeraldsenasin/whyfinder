"""Read `params.yaml`, the single home of every tunable (DVC tracks it)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path("params.yaml")


class ParamError(KeyError):
    """A parameter is missing or has the wrong type."""


def load_params(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Parse the YAML file into a dict."""
    with path.open(encoding="utf-8") as f:
        params = yaml.safe_load(f)
    if not isinstance(params, dict):
        raise ParamError(f"{path}: top level must be a mapping")
    return params


def param[T](params: dict[str, Any], dotted: str, kind: type[T]) -> T:
    """`param(p, "data.kcore", int)` → p["data"]["kcore"], checked to be an int.

    An int is accepted where a float is asked for; a bool is never accepted as a number.
    """
    node: Any = params
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise ParamError(f"missing parameter {dotted!r}")
        node = node[key]
    if kind is float and isinstance(node, int) and not isinstance(node, bool):
        node = float(node)
    if not isinstance(node, kind) or (kind is not bool and isinstance(node, bool)):
        raise ParamError(f"parameter {dotted!r} must be {kind.__name__}, got {node!r}")
    return node
