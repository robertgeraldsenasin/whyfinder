"""The NLI cross-encoder judge, with transformers and torch replaced by small fakes."""

from __future__ import annotations

import contextlib
import importlib
import json
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from whyfinder.rag.nli import CrossEncoder


class Net:
    def __init__(self, labels: dict[int, str]) -> None:
        self.config = SimpleNamespace(id2label=labels, _commit_hash="abc123")

    def eval(self) -> None:
        pass

    def __call__(self, **batch: str) -> Any:
        scores = [0.1, 0.9, 0.0] if "yes" in batch["hypothesis"] else [0.8, 0.1, 0.1]
        return SimpleNamespace(logits=[scores])


def fakes(labels: dict[int, str]) -> dict[str, Any]:
    torch = SimpleNamespace(
        manual_seed=lambda _: None,
        no_grad=contextlib.nullcontext,
        argmax=lambda xs: SimpleNamespace(item=lambda: max(range(len(xs)), key=xs.__getitem__)),
    )
    transformers = SimpleNamespace(
        AutoTokenizer=SimpleNamespace(
            from_pretrained=lambda _: lambda p, h, **_k: {"premise": p, "hypothesis": h}
        ),
        AutoModelForSequenceClassification=SimpleNamespace(from_pretrained=lambda _: Net(labels)),
    )
    return {"torch": torch, "transformers": transformers}


def use(monkeypatch: pytest.MonkeyPatch, modules: dict[str, Any]) -> None:
    real = importlib.import_module

    def fake(name: str, package: str | None = None) -> ModuleType | Any:
        if name in modules:
            return modules[name]
        if name in ("torch", "transformers"):
            raise ImportError(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", fake)


def test_the_pair_goes_in_and_a_judge_label_comes_out(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, fakes({0: "CONTRADICTION", 1: "ENTAILMENT", 2: "NEUTRAL"}))
    nli = CrossEncoder("nli:cross-encoder/x")
    assert nli.digest == "abc123"
    yes = nli.complete(json.dumps(["facts", "yes it follows"]), seed=1, schema={})
    no = nli.complete(json.dumps(["facts", "it does not"]), seed=1, schema={})
    assert json.loads(yes) == {"label": "entailed"}
    assert json.loads(no) == {"label": "contradicted"}


def test_unknown_labels_and_names_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="starts with 'nli:'"):
        CrossEncoder("qwen2.5:7b")
    use(monkeypatch, fakes({0: "positive", 1: "negative"}))
    with pytest.raises(RuntimeError, match="cannot read"):
        _ = CrossEncoder("nli:x").digest


def test_without_transformers_it_says_to_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, {})
    with pytest.raises(RuntimeError, match="replay the cache"):
        CrossEncoder("nli:x").complete(json.dumps(["a", "b"]), seed=1, schema={})
