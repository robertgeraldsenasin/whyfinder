from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from whyfinder.cli import app
from whyfinder.export.reviews import (
    MAX_WORDS,
    Quote,
    best_sentence,
    clean_text,
    cover,
    displayable,
    distinctive_terms,
    doc_frequencies,
    polarity,
    review_evidence,
    tidy,
    tokens,
)


def test_clean_text_strips_bbcode_urls_and_spaces() -> None:
    assert clean_text("[h1]Great[/h1]  see https://x.io  [b]now[/b]") == "Great see now"


def test_polarity_handles_negation() -> None:
    assert polarity(tokens("a beautiful and relaxing game")) == (2, 0)
    assert polarity(tokens("not fun at all, boring")) == (0, 2)


@pytest.mark.parametrize(
    ("sentence", "ok"),
    [
        ("The music in this game is beautiful and the story stays with you.", True),
        ("THIS GAME IS THE BEST GAME EVER MADE IN THE WORLD.", False),
        ("This is a fucking great game and you should buy it.", False),
        ("Early Access Review: it is fun and it is great.", False),
        ("☐ Bad ☑ Good ☐ Very good ☐ Masterpiece of the year.", False),
        ("Juego muy bueno y divertido.", False),
    ],
)
def test_displayable(sentence: str, ok: bool) -> None:
    assert displayable(sentence) is ok


def test_best_sentence_picks_a_short_positive_sentence() -> None:
    text = (
        "I bought it on sale. This game is a masterpiece and the soundtrack is wonderful. "
        "The ending was bad. " + "word " * 40
    )
    found = best_sentence(text, frozenset({"soundtrack"}))
    assert found is not None
    sentence, score = found
    assert sentence == "This game is a masterpiece and the soundtrack is wonderful."
    # two positive words, one top term that is also its one content word, well formed
    assert score == pytest.approx(2 + 0.8 + 0.25 + 0.5)
    assert best_sentence("It is bad and boring and I want a refund now.", frozenset()) is None


def test_best_sentence_respects_the_word_limit() -> None:
    long = "This wonderful game " + "and it keeps going " * 10 + "forever."
    assert best_sentence(long, frozenset()) is None
    found = best_sentence("Simply put this game is fun with friends", frozenset())
    assert found is not None
    assert found[0].endswith(".")
    assert len(found[0].split()) <= MAX_WORDS


def test_distinctive_terms_find_what_sets_a_game_apart() -> None:
    docs = {
        1: [{"soundtrack", "story"} for _ in range(30)] + [{"shooter"} for _ in range(5)],
        2: [{"shooter", "aim"} for _ in range(30)] + [{"story"} for _ in range(5)],
    }
    freq = {g: doc_frequencies(d) for g, d in docs.items()}
    counts = {g: c for g, (c, _) in freq.items()}
    sizes = {g: n for g, (_, n) in freq.items()}
    assert sizes == {1: 35, 2: 35}
    terms = distinctive_terms(counts, sizes, top=3, min_docs=5, prior=10.0, min_z=1.0)
    assert {t for t, _ in terms[1][:2]} == {"soundtrack", "story"}
    assert terms[2][0][0] in {"aim", "shooter"}
    assert "story" not in [t for t, _ in terms[2]]
    excluded = distinctive_terms(
        counts, sizes, top=3, min_docs=5, prior=10.0, min_z=1.0, exclude={1: {"story"}}
    )
    assert "story" not in [t for t, _ in excluded[1]]


def frame() -> pd.DataFrame:
    rows = []
    rid = 0
    for user in range(12):
        for game in (10, 20, 30):
            if (user + game) % 4 == 0:
                continue
            text = (
                f"After {user} runs the soundtrack is wonderful and the exploration is beautiful."
                if game == 10
                else f"After {user} matches it is a brilliant shooter with satisfying aim and maps."
            )
            rows.append((rid, f"u{user:015d}", game, float(user * 10), 2016, text))
            rid += 1
    rows.append((rid, "u000000000000099", 10, 3.0, 2016, "This is shit, do not buy it."))
    return pd.DataFrame(rows, columns=["review_id", "user", "game", "hours", "year", "text"])


def test_review_evidence_bridges_players_across_games() -> None:
    games = [
        {"id": 10, "title": "Game Ten"},
        {"id": 20, "title": "Twenty"},
        {"id": 99, "title": "Empty"},
    ]
    out = review_evidence(
        frame(), games, quotes_per_game=3, terms_per_game=5, min_docs=3, prior=1.0
    )
    ten = out["games"]["10"]
    assert len(ten["quotes"]) == 3
    assert all(len(q["text"].split()) <= MAX_WORDS for q in ten["quotes"])
    assert all("shit" not in q["text"] for q in ten["quotes"])
    assert [q["hours"] for q in ten["quotes"]] == sorted(
        (q["hours"] for q in ten["quotes"]), reverse=True
    )
    assert any(1 in q["also"] for q in ten["quotes"])  # reviewers who also reviewed game 20
    assert all(0 not in q["also"] for q in ten["quotes"])  # never the game itself
    assert "soundtrack" in [t for t, _ in ten["terms"]]
    assert out["games"]["99"] == {"terms": [], "quotes": []}
    assert "u000" not in json.dumps(out)  # no user IDs leave the pipeline


def test_export_reviews_cli(tmp_path: Path) -> None:
    interim, export = tmp_path / "data" / "interim", tmp_path / "data" / "export"
    interim.mkdir(parents=True)
    export.mkdir(parents=True)
    df = frame()
    meta = df.rename(columns={"user": "username"}).assign(date="2016-03-01")
    meta.loc[meta.index[:3], "date"] = "2019-01-01"  # after T1: excluded
    meta[["review_id", "username", "game", "hours", "date"]].to_parquet(interim / "reviews.parquet")
    df[["review_id", "game", "text"]].to_parquet(interim / "review_text.parquet")
    (tmp_path / "data" / "split.json").write_text(json.dumps({"t1": "2017-05-31"}))
    (export / "demo-slice.json").write_text(
        json.dumps({"games": [{"id": 10, "title": "Ten"}, {"id": 20, "title": "Twenty"}]})
    )
    (tmp_path / "params.yaml").write_text(
        "data: {user_salt: s}\ndemo: {quotes_per_game: 2, terms_per_game: 4, reviews_per_game: 5}\n"
    )
    old = Path.cwd()
    os.chdir(tmp_path)
    try:
        result = CliRunner().invoke(app, ["export", "reviews"])
    finally:
        os.chdir(old)
    assert result.exit_code == 0, result.output
    payload = json.loads((export / "reviews.json").read_text())
    assert set(payload["games"]) == {"10", "20"}
    assert len(payload["games"]["20"]["quotes"]) == 2
    kept = meta["game"].isin([10, 20]) & (meta["date"] < "2017")
    assert f"from 10 of {int(kept.sum())} reviews before 2017-05-31" in result.output


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Conclusion: A beautiful story and a fun world.", "A beautiful story and a fun world."),
        (
            "Specal Ops , Multiplayer and more , all fun.",
            "Specal Ops, Multiplayer and more, all fun.",
        ),
        ("It is worth it in my opinion,.", "It is worth it in my opinion."),
        (
            "Awesome game and multiplayer is just so fun!!!!!",
            "Awesome game and multiplayer is just so fun!",
        ),
    ],
)
def test_tidy_keeps_words_and_fixes_punctuation(raw: str, clean: str) -> None:
    assert tidy(raw) == clean


@pytest.mark.parametrize(
    "text",
    [
        "But I still remember all the great and scary fun I had with it.",
        "This used to be my favorite game until the publisher ruined it.",
        "The music is awesome and the game is pretty fun, but that's it.",
        "I LOVE it......a great game with great scares and more.",
        "Even when the hackers came it was still a pretty fun game.",
    ],
)
def test_best_sentence_skips_fragments_and_backhanded_praise(text: str) -> None:
    assert best_sentence(text, frozenset()) is None


def test_well_formed_sentences_score_higher() -> None:
    a = best_sentence("A wonderful game with a lovely story.", frozenset())
    b = best_sentence("a wonderful game with a lovely story", frozenset())
    assert a is not None
    assert b is not None
    assert a[1] == b[1] + 0.5


def test_distinctive_terms_merge_plurals() -> None:
    docs = {1: [{"quest", "quests"} for _ in range(20)], 2: [{"aim"} for _ in range(20)]}
    freq = {g: doc_frequencies(d) for g, d in docs.items()}
    counts = {g: c for g, (c, _) in freq.items()}
    sizes = {g: n for g, (_, n) in freq.items()}
    terms = distinctive_terms(counts, sizes, top=5, min_docs=5, prior=10.0, min_z=1.0)
    assert [t for t, _ in terms[1]] == ["quest"]


def test_cover_spreads_quotes_across_neighbour_games() -> None:
    def q(rid: int, score: float, also: list[int], text: str = "") -> Quote:
        return Quote(text or f"Quote {rid}.", 10.0, 2016, also, score, rid)

    weight = {1: 1.0, 2: 0.5, 3: 0.25}
    pool = [
        q(1, 5.0, [1]),
        q(2, 4.9, [1]),
        q(3, 4.0, [2, 3]),
        q(4, 1.0, []),
        q(5, 5.0, [1], "Quote 1."),
    ]
    assert [x.review_id for x in cover(pool, weight, 3)] == [1, 3, 2]
    assert [x.review_id for x in cover(pool, weight, 9)] == [1, 3, 2, 4]  # duplicate text dropped
    assert cover([], weight, 3) == []


def test_generic_praise_is_not_quoted() -> None:
    assert best_sentence("It is still great, great fun to play.", frozenset()) is None
    assert best_sentence("This is the BEST game on Steam.", frozenset()) is None
    specific = best_sentence(
        "The puzzles twist portals in clever and satisfying ways.", frozenset()
    )
    assert specific is not None
