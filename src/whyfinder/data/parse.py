"""Streaming parsers for the UCSD Steam files (FR-02).

The files hold one Python-literal dict per line (single quotes, `True`, `None`), not JSON.
Each line is parsed with `ast.literal_eval`, never `eval`, and never by loading the whole file.
Malformed lines are counted; more than `tolerance` of them (default 0.1%) is an error.
"""

from __future__ import annotations

import ast
import gzip
import multiprocessing
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

BATCH_LINES = 20_000
WRITE_ROWS = 200_000
DEFAULT_TOLERANCE = 0.001

Record = dict[str, Any]


class ParseError(RuntimeError):
    """Too many malformed lines."""


@dataclass(frozen=True)
class ParseStats:
    """Counts from one parse."""

    lines: int
    malformed: int
    written: int

    @property
    def malformed_share(self) -> float:
        return self.malformed / self.lines if self.lines else 0.0


def parse_line(line: bytes) -> Record | None:
    """One line → dict, or None if it is not a Python-literal dict."""
    text = line.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _parse_batch(lines: list[bytes]) -> list[Record | None]:
    return [parse_line(line) for line in lines]


def _batches(path: Path) -> Iterator[list[bytes]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        batch: list[bytes] = []
        for line in f:
            if not line.strip():
                continue
            batch.append(line)
            if len(batch) == BATCH_LINES:
                yield batch
                batch = []
        if batch:
            yield batch


def iter_records(path: Path, workers: int = 1) -> Iterator[Record | None]:
    """Yield each non-blank line parsed (None when malformed), in file order.

    With `workers > 1`, batches of lines are parsed in a process pool; order is preserved.
    """
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if workers == 1:
        for batch in _batches(path):
            yield from _parse_batch(batch)
        return
    context = multiprocessing.get_context("spawn")  # fork is unsafe in threaded parents
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        for parsed in pool.map(_parse_batch, _batches(path), chunksize=1):
            yield from parsed


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # drop NaN


def _strings(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [s for s in (_text(v) for v in value) if s]


def _price(value: object) -> float | None:
    number = _float(value)
    if number is not None:
        return number
    text = _text(value)
    if text and "free" in text.lower():
        return 0.0
    return None


REVIEW_SCHEMA = pa.schema(
    [
        ("review_id", pa.int64()),
        ("username", pa.string()),
        ("steam_user_id", pa.string()),
        ("game", pa.int64()),
        ("hours", pa.float64()),
        ("date", pa.string()),
        ("early_access", pa.bool_()),
        ("found_funny", pa.int64()),
    ]
)
TEXT_SCHEMA = pa.schema([("review_id", pa.int64()), ("game", pa.int64()), ("text", pa.string())])
GAME_SCHEMA = pa.schema(
    [
        ("game", pa.int64()),
        ("title", pa.string()),
        ("developer", pa.string()),
        ("publisher", pa.string()),
        ("genres", pa.list_(pa.string())),
        ("tags", pa.list_(pa.string())),
        ("specs", pa.list_(pa.string())),
        ("price", pa.float64()),
        ("release_date", pa.string()),
        ("early_access", pa.bool_()),
        ("sentiment", pa.string()),
        ("metascore", pa.float64()),
    ]
)


def review_row(review_id: int, record: Record) -> Record:
    """Map one raw review dict to the interim review columns."""
    early = record.get("early_access")
    return {
        "review_id": review_id,
        "username": _text(record.get("username")),
        "steam_user_id": _text(record.get("user_id")),
        "game": _int(record.get("product_id")),
        "hours": _float(record.get("hours")),
        "date": _text(record.get("date")),
        "early_access": early if isinstance(early, bool) else None,
        "found_funny": _int(record.get("found_funny")),
    }


def game_row(record: Record) -> Record | None:
    """Map one raw game dict to the interim game columns; None when it has no usable ID."""
    game = _int(record.get("id"))
    if game is None:
        return None
    early = record.get("early_access")
    developer = record.get("developer")
    publisher = record.get("publisher")
    return {
        "game": game,
        "title": _text(record.get("title")) or _text(record.get("app_name")),
        "developer": _text(", ".join(developer) if isinstance(developer, list) else developer),
        "publisher": _text(", ".join(publisher) if isinstance(publisher, list) else publisher),
        "genres": _strings(record.get("genres")),
        "tags": _strings(record.get("tags")),
        "specs": _strings(record.get("specs")),
        "price": _price(record.get("price")),
        "release_date": _text(record.get("release_date")),
        "early_access": early if isinstance(early, bool) else None,
        "sentiment": _text(record.get("sentiment")),
        "metascore": _float(record.get("metascore")),
    }


class _Writer:
    """Buffered Parquet writer that always produces a file, even with zero rows."""

    def __init__(self, path: Path, schema: pa.Schema) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.schema = schema
        self.writer = pq.ParquetWriter(path, schema, compression="zstd")
        self.rows: list[Record] = []
        self.written = 0

    def add(self, row: Record) -> None:
        self.rows.append(row)
        if len(self.rows) >= WRITE_ROWS:
            self.flush()

    def flush(self) -> None:
        if self.rows:
            self.writer.write_table(pa.Table.from_pylist(self.rows, schema=self.schema))
            self.written += len(self.rows)
            self.rows = []

    def close(self) -> int:
        self.flush()
        self.writer.close()
        return self.written


def _check(path: Path, lines: int, malformed: int, tolerance: float) -> None:
    if lines and malformed / lines > tolerance:
        raise ParseError(
            f"{path.name}: {malformed} of {lines} lines malformed "
            f"({malformed / lines:.3%} > {tolerance:.3%})"
        )


def parse_reviews(
    raw: Path,
    out_reviews: Path,
    out_text: Path,
    *,
    workers: int = 1,
    tolerance: float = DEFAULT_TOLERANCE,
) -> ParseStats:
    """Parse Version 2 reviews into interaction columns and a separate text table (for M3).

    `review_id` is the 0-based index of the review among the non-blank lines, so it is stable
    across runs and links the two tables.
    """
    reviews = _Writer(out_reviews, REVIEW_SCHEMA)
    texts = _Writer(out_text, TEXT_SCHEMA)
    lines = malformed = 0
    for review_id, record in enumerate(iter_records(raw, workers)):
        lines += 1
        if record is None:
            malformed += 1
            continue
        row = review_row(review_id, record)
        reviews.add(row)
        text = _text(record.get("text"))
        if text is not None:
            texts.add({"review_id": review_id, "game": row["game"], "text": text})
    written = reviews.close()
    texts.close()
    _check(raw, lines, malformed, tolerance)
    return ParseStats(lines, malformed, written)


def parse_games(
    raw: Path,
    out_games: Path,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    row: Callable[[Record], Record | None] = game_row,
) -> ParseStats:
    """Parse Version 2 game metadata. Rows without an ID are skipped (counted in stats, not errors);
    for duplicate IDs the first row wins."""
    games = _Writer(out_games, GAME_SCHEMA)
    seen: set[int] = set()
    lines = malformed = 0
    for record in iter_records(raw):
        lines += 1
        if record is None:
            malformed += 1
            continue
        mapped = row(record)
        if mapped is None or mapped["game"] in seen:
            continue
        seen.add(mapped["game"])
        games.add(mapped)
    written = games.close()
    _check(raw, lines, malformed, tolerance)
    return ParseStats(lines, malformed, written)
