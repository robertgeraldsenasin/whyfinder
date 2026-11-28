"""Grounded generation (FR-16; ADR-0009): prompts, the cache, retries and the fallback."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from whyfinder.rag.claims import (
    AttributionRef,
    CounterfactualRef,
    ReviewRef,
    SchemaError,
    Source,
)
from whyfinder.rag.generate import (
    Cache,
    Cached,
    CacheMissError,
    LlmUnavailableError,
    Ollama,
    Pack,
    explain,
    facts,
    literal,
    pinned,
    prompt,
    read,
    schema,
    template,
)

QUOTE = "Tight, fast combat and a soundtrack that never lets up."
PACK = Pack(
    pick_title="Hades",
    liked=(("3", "Celeste"), ("1", "Dead Cells"), ("2", "Hollow Knight")),
    attributions=(("1", "Dead Cells", 0.5), ("2", "Hollow Knight", 0.3), ("3", "Celeste", 0.2)),
    removed=(("1", "Dead Cells"),),
    paths=("shares the tag Roguelite with Dead Cells",),
    kept_for_variety=True,
    quotes=(("c_7_0", "combat", QUOTE),),
)
SOURCE = Source(
    pick_title="Hades",
    attributions={"1": ("Dead Cells", 0.5), "2": ("Hollow Knight", 0.3), "3": ("Celeste", 0.2)},
    chunks={"c_7_0": QUOTE},
    removed=frozenset({"1"}),
    catalogue=("Dead Cells", "Hollow Knight", "Celeste", "Hades", "Dota 2"),
)
GOOD = json.dumps({"claims": [{"fact": "A1", "text": "Dead Cells carries it (50%)."}]})
BAD = json.dumps({"claims": [{"fact": "A1", "text": "Dota 2 carries it (50%)."}]})
NO_SCHEMA: dict[str, Any] = {}


class Script:
    model = "script"
    digest = "sha256:script"

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.schemas: list[dict[str, Any]] = []

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return self.answers.pop(0)


def test_facts_carry_ids_and_the_evidence_behind_them() -> None:
    listed = facts(PACK)
    assert [f.id for f in listed] == ["A1", "A2", "A3", "C1", "Q1"]
    assert listed[0].line == "Dead Cells counted for 50% of the score"
    assert listed[0].evidence == AttributionRef("1", 0.5)
    assert listed[3].evidence == CounterfactualRef(("1",))
    assert listed[4].evidence == ReviewRef("c_7_0", QUOTE)
    blind = facts(PACK, with_attributions=False)
    assert [(f.id, f.line) for f in blind] == [
        ("L1", "Celeste"),
        ("L2", "Dead Cells"),
        ("L3", "Hollow Knight"),
    ]


def test_the_prompt_lists_the_facts_and_the_ablation_hides_the_shares() -> None:
    full = prompt(PACK)
    for fact in (
        "Write in English",
        "Recommended game: Hades",
        "Games the player liked, with the share of the reasons for this pick each supplied:\n"
        "A1: Dead Cells, 50%\nA2: Hollow Knight, 30%\nA3: Celeste, 20%\n",
        "Had the player not liked these games, Hades would not have been recommended:\n"
        "C1: Dead Cells\n",
        f"What players of Hades wrote:\nQ1: on combat, \u201c{QUOTE}\u201d\n",
        "one or two sentences of at most 25 words each",
        "Also true, may be mentioned but has no ID: "
        "Hades shares the tag Roguelite with Dead Cells.",
        "End every sentence with a full stop.",
    ):
        assert fact in full
    # Facts are listed as data, not as the sentences a model could copy back.
    assert "counted for 50% of the score" not in full
    bare = prompt(PACK, with_attributions=False)
    assert "50%" not in bare
    assert QUOTE not in bare
    assert "Games the player liked:\nL1: Celeste\nL2: Dead Cells\nL3: Hollow Knight\n" in bare
    again = prompt(PACK, feedback=["wrong share for Dead Cells"])
    assert again.startswith(full)
    assert "- wrong share for Dead Cells" in again


def test_the_schema_pins_each_sentence_to_its_fact() -> None:
    listed = facts(PACK)
    s = schema(listed)
    options = s["properties"]["claims"]["items"]["anyOf"]
    assert [o["properties"]["fact"]["enum"] for o in options] == [[f.id] for f in listed]
    assert s["properties"]["claims"]["maxItems"] == 2  # the template may use three
    by_id = {f.id: f.pattern for f in listed}
    fits = {
        "A1": [
            "Dead Cells is the main reason (50%).",
            "You liked Dead Cells, so here it is!",
            "Half of this pick, 50%, comes from the hours you put into Dead Cells.",
        ],
        "C1": ["Take Dead Cells off your list and Hades drops out."],
        "Q1": [f"One player puts it simply: \u201c{QUOTE}\u201d.", f"\u201c{QUOTE}\u201d"],
    }
    misses = {
        "A1": [
            "Hades is great.",
            "Dead Cells drove 90% of it.",
            'Dead Cells, "they" say.',
            "Dead Cells is the main reason, making it",  # cut off: no full stop
            "Dead Cells " + "and more " * 20 + ".",  # past the bound
            "Dead Cells is the main reason. {",  # JSON debris
            "Dead Cells is the main reason [1].",
            "Dead Cells is the main\nreason.",
        ],
        "C1": ["Take Dead Cells off your list and Hades drops out"],
        "Q1": [f'Players say "{QUOTE}"', f"\u201c{QUOTE[:-1]}\u201d"],
    }
    for fid, texts in fits.items():
        assert all(re.fullmatch(by_id[fid], x) for x in texts), fid
    for fid, texts in misses.items():
        assert not any(re.fullmatch(by_id[fid], x) for x in texts), fid


def test_titles_are_pinned_literally_and_odd_quotes_left_out() -> None:
    odd = Pack(
        **{
            **PACK.__dict__,
            "attributions": (("9", "S.T.A.L.K.E.R.: Call of Pripyat (2010)", 0.6),),
            "removed": (),
            "quotes": (("c_1_0", "story", 'He said "wow"'), ("c_1_1", "story", "Fine.")),
        }
    )
    listed = facts(odd)
    assert [f.id for f in listed] == ["A1", "Q1"]
    a1 = listed[0].pattern
    assert re.fullmatch(a1, "Because of S.T.A.L.K.E.R.: Call of Pripyat (2010).")
    assert not re.fullmatch(a1, "Because of SxTxAxLxKxExRx: Call of Pripyat (2010).")
    assert literal("a.b(c)") == "a\\.b\\(c\\)"
    marked = pinned("BioShock\u00ae 2: Total War\u2122")
    assert re.fullmatch(marked, "BioShock 2: Total War")
    assert re.fullmatch(marked, "BioShock\u00ae 2: Total War\u2122")
    assert not re.fullmatch(marked, "BioShock 3: Total War")


def test_reading_an_answer_attaches_each_facts_evidence() -> None:
    raw = json.dumps(
        {"claims": [{"fact": "A1", "text": "Dead Cells."}, {"fact": "C1", "text": "Hades."}]}
    )
    first, second = read(raw, facts(PACK))
    assert first.evidence == (AttributionRef("1", 0.5),)
    assert second.evidence == (CounterfactualRef(("1",)),)
    for bad in (
        "nope",
        "[]",
        '{"claims": [], "x": 1}',
        '{"claims": [{"text": "x"}]}',
        '{"claims": [{"fact": "A1", "text": " "}]}',
        '{"claims": [{"fact": "Z9", "text": "x"}]}',
        '{"claims": [{"fact": ["A1"], "text": "x"}]}',
        json.dumps({"claims": [{"fact": "A1", "text": "x"}] * 4}),
    ):
        with pytest.raises(SchemaError):
            read(bad, facts(PACK))


def test_a_faithful_answer_is_kept() -> None:
    backend = Script(GOOD)
    out = explain(PACK, SOURCE, backend, lambda: template(PACK), seed=1)
    assert backend.schemas[0] == schema(facts(PACK))
    assert out.used == "model"
    assert not out.fallback_used
    assert out.claims[0].text == "Dead Cells carries it (50%)."


def test_a_rejected_answer_gets_one_retry_with_the_reasons() -> None:
    backend = Script(BAD, GOOD)
    out = explain(PACK, SOURCE, backend, lambda: template(PACK), seed=1)
    assert out.used == "model-retry"
    assert "Dota 2" in backend.prompts[1]
    assert out.attempts[0].reasons


def test_two_rejections_fall_back_to_the_template() -> None:
    out = explain(PACK, SOURCE, Script("{}", BAD), lambda: template(PACK), seed=1)
    assert out.used == "template"
    assert out.fallback_used
    assert "claim schema" in out.attempts[0].reasons[0]
    assert out.claims == template(PACK)
    empty = explain(PACK, SOURCE, Script('{"claims": []}', '{"claims": []}'), lambda: [], seed=1)
    assert empty.attempts[0].reasons == ["no claims"]


def test_the_template_is_faithful_and_within_limits() -> None:
    from whyfinder.rag.claims import check

    claims = template(PACK)
    assert [c.text for c in claims] == [
        "Dead Cells is the biggest driver of this pick (50%).",
        "Hollow Knight adds 30%.",
        f'Players of Hades mention combat: "{QUOTE}"',
    ]
    assert check(claims, SOURCE) == []
    small = Pack(**{**PACK.__dict__, "attributions": (("1", "Dead Cells", 0.95), ("2", "B", 0.05))})
    assert len([c for c in template(small) if isinstance(c.evidence[0], AttributionRef)]) == 1


def test_the_cache_replays_and_refuses_misses(tmp_path: Path) -> None:
    path = tmp_path / "cache.jsonl"
    filling = Cached(Cache.load(path), "script", "sha256:script", inner=Script(GOOD))
    assert filling.complete("p", seed=3, schema=NO_SCHEMA) == GOOD
    filling.cache.save()
    replay = Cached(Cache.load(path), "script", "sha256:script")
    assert replay.complete("p", seed=3, schema=NO_SCHEMA) == GOOD
    with pytest.raises(CacheMissError, match="no cached generation"):
        replay.complete("p", seed=4, schema=NO_SCHEMA)
    with pytest.raises(CacheMissError):
        replay.complete("p", seed=3, schema={"type": "object"})
    other_model = Cached(Cache.load(path), "script", "sha256:other")
    with pytest.raises(CacheMissError):
        other_model.complete("p", seed=3, schema=NO_SCHEMA)
    row = json.loads(path.read_text().splitlines()[0])
    assert set(row) == {"key", "model", "digest", "seed", "prompt_sha256", "response"}
    Cache(tmp_path / "empty.jsonl").save()
    assert (tmp_path / "empty.jsonl").read_text() == ""


@pytest.fixture
def server() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    seen: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            return

        def reply(self, body: dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            self.reply({"models": [{"name": "tiny:latest", "digest": "abc123"}]})

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            seen.append(body)
            if body.get("model") == "picky":
                self.reply({"error": "failed to load model vocabulary required for format"}, 400)
                return
            if body.get("model") == "loops":
                self.reply({"error": "prediction aborted, token repeat limit reached"}, 500)
                return
            self.reply({"response": GOOD})

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", seen
    finally:
        httpd.shutdown()


def test_ollama_asks_for_schema_constrained_deterministic_output(
    server: tuple[str, list[dict[str, Any]]],
) -> None:
    url, seen = server
    llm = Ollama("tiny", url=url)
    assert llm.digest == "abc123"
    assert llm.complete("hello", seed=7, schema=schema(facts(PACK))) == GOOD
    sent = seen[0]
    assert sent["model"] == "tiny"
    assert sent["stream"] is False
    assert sent["options"]["temperature"] == 0
    assert sent["options"]["seed"] == 7
    assert sent["format"] == schema(facts(PACK))
    with pytest.raises(LlmUnavailableError, match="not pulled"):
        _ = Ollama("missing", url=url).digest
    # Ollama's own reason for refusing a request reaches the error, not just the status line.
    with pytest.raises(LlmUnavailableError, match=r"400.*failed to load model vocabulary"):
        Ollama("picky", url=url).complete("hello", seed=7, schema={})
    # A model stuck repeating itself is a failed answer, not a failed server.
    stopped = Ollama("loops", url=url).complete("hello", seed=7, schema={})
    assert json.loads(stopped) == {"error": "prediction aborted"}
    with pytest.raises(SchemaError, match="the model was stopped: prediction aborted"):
        read(stopped, facts(PACK))


def test_ollama_reports_an_unreachable_server() -> None:
    with pytest.raises(LlmUnavailableError):
        Ollama("tiny", url="http://127.0.0.1:9", timeout=0.5).complete("x", seed=1, schema={})
    with pytest.raises(LlmUnavailableError, match="not an HTTP URL"):
        Ollama("tiny", url="file:///etc/passwd").complete("x", seed=1, schema={})
