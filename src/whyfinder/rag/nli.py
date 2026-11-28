"""An NLI cross-encoder as an entailment judge (06_RAG "Evaluation"; ADR-0009).

The spec's entailment measure: a cross-encoder trained on natural-language inference reads the
facts (premise) and one generated sentence (hypothesis) together and says entailment, neutral or
contradiction. It sits behind the same `Backend` interface as an Ollama model, so its answers go
through the generation cache and CI replays them without loading it: the "prompt" is the JSON pair
[premise, hypothesis] and the answer the JSON label.

Hugging Face transformers and torch are not dependencies. The llm workflow installs them for the
run that fills the cache; nothing else imports them.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from typing import Any

from whyfinder.rag.judge import NLI

LABELS = {"entailment": "entailed", "neutral": "neutral", "contradiction": "contradicted"}


@dataclass
class CrossEncoder:
    """`model` is "nli:<Hugging Face model id>"; weights load on first use, on the CPU."""

    model: str
    _loaded: tuple[Any, Any, dict[int, str], str] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.model.startswith(NLI):
            raise ValueError(f"an NLI judge's name starts with {NLI!r}, got {self.model!r}")

    def _load(self) -> tuple[Any, Any, dict[int, str], str]:
        if self._loaded is None:
            try:
                transformers = importlib.import_module("transformers")
                torch = importlib.import_module("torch")
            except ImportError as exc:
                raise RuntimeError(
                    "the NLI judge needs torch and transformers, which only the llm workflow "
                    "installs; replay the cache instead"
                ) from exc
            torch.manual_seed(0)
            name = self.model.removeprefix(NLI)
            tokenizer = transformers.AutoTokenizer.from_pretrained(name)
            network = transformers.AutoModelForSequenceClassification.from_pretrained(name)
            network.eval()
            names = {int(i): str(n).lower() for i, n in network.config.id2label.items()}
            unknown = set(names.values()) - set(LABELS)
            if unknown:
                raise RuntimeError(f"{name} has labels this judge cannot read: {sorted(unknown)}")
            revision = str(getattr(network.config, "_commit_hash", None) or "unknown")
            self._loaded = (tokenizer, network, names, revision)
        return self._loaded

    @property
    def digest(self) -> str:
        return self._load()[3]

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        """The label for the [premise, hypothesis] pair in `prompt`, as {"label": ...}."""
        premise, hypothesis = json.loads(prompt)
        tokenizer, network, names, _ = self._load()
        torch = importlib.import_module("torch")
        batch = tokenizer(premise, hypothesis, return_tensors="pt", truncation=True)
        with torch.no_grad():
            logits = network(**batch).logits[0]
        best = int(torch.argmax(logits).item())
        return json.dumps({"label": LABELS[names[best]]})
