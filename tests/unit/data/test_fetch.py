from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import BinaryIO

import pytest

from whyfinder.data import fetch as fetch_module
from whyfinder.data.fetch import (
    ChecksumMismatchError,
    ChecksumMissingError,
    DownloadError,
    download,
    fetch,
    read_checksums,
    sha256_file,
    urlopen,
    write_checksums,
)
from whyfinder.data.sources import SOURCES

PAYLOAD = b"{'id': '1'}\n" * 1000


class FakeNet:
    """Serves fixed bytes per URL; fails the first `failures` calls with an OSError."""

    def __init__(self, body: bytes = PAYLOAD, failures: int = 0) -> None:
        self.body = body
        self.failures = failures
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> BinaryIO:
        self.calls.append(url)
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionResetError("reset by peer")
        return io.BytesIO(self.body)


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    path.write_bytes(PAYLOAD)
    assert sha256_file(path) == hashlib.sha256(PAYLOAD).hexdigest()


def test_checksums_round_trip_sorted(tmp_path: Path) -> None:
    path = tmp_path / "checksums.txt"
    write_checksums(path, {"b.gz": "b" * 64, "a.gz": "a" * 64})
    assert path.read_text().splitlines() == [f"{'a' * 64}  a.gz", f"{'b' * 64}  b.gz"]
    assert read_checksums(path) == {"a.gz": "a" * 64, "b.gz": "b" * 64}


def test_read_checksums_ignores_comments_and_missing_file(tmp_path: Path) -> None:
    assert read_checksums(tmp_path / "absent.txt") == {}
    path = tmp_path / "c.txt"
    path.write_text(f"# header\n\n{'C' * 64}  x.gz\n")
    assert read_checksums(path) == {"x.gz": "c" * 64}


def test_read_checksums_rejects_malformed_line(tmp_path: Path) -> None:
    path = tmp_path / "c.txt"
    path.write_text("deadbeef  x.gz\n")
    with pytest.raises(ValueError, match="expected"):
        read_checksums(path)


def test_download_retries_with_exponential_backoff(tmp_path: Path) -> None:
    net, sleeps = FakeNet(failures=2), []
    dest = tmp_path / "x.gz"
    download("https://example.org/x.gz", dest, opener=net, sleep=sleeps.append)
    assert dest.read_bytes() == PAYLOAD
    assert sleeps == [2.0, 4.0]
    assert not dest.with_name("x.gz.part").exists()


def test_download_gives_up_and_cleans_partial_file(tmp_path: Path) -> None:
    dest = tmp_path / "x.gz"
    with pytest.raises(DownloadError, match="3 attempts"):
        download(
            "https://e.org/x", dest, opener=FakeNet(failures=9), retries=3, sleep=lambda _: None
        )
    assert not dest.exists()
    assert not dest.with_name("x.gz.part").exists()


def test_download_rejects_zero_retries(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="retries"):
        download("https://e.org/x", tmp_path / "x", opener=FakeNet(), retries=0)


def test_urlopen_refuses_plain_http() -> None:
    with pytest.raises(ValueError, match="non-HTTPS"):
        urlopen("http://example.org/x", 1.0)


def test_fetch_records_then_keeps(tmp_path: Path) -> None:
    raw, sums, net = tmp_path / "raw", tmp_path / "checksums.txt", FakeNet()
    first = fetch(raw, sums, ["games"], record=True, opener=net, sleep=lambda _: None)
    assert [r.action for r in first] == ["recorded"]
    assert read_checksums(sums) == {"steam_games.json.gz": hashlib.sha256(PAYLOAD).hexdigest()}
    second = fetch(raw, sums, ["games"], opener=net, sleep=lambda _: None)
    assert [r.action for r in second] == ["kept"]
    assert net.calls == [SOURCES["games"].url]


def test_fetch_redownloads_a_corrupt_file(tmp_path: Path) -> None:
    raw, sums = tmp_path / "raw", tmp_path / "checksums.txt"
    write_checksums(sums, {"steam_games.json.gz": hashlib.sha256(PAYLOAD).hexdigest()})
    raw.mkdir()
    (raw / "steam_games.json.gz").write_bytes(b"truncated")
    result = fetch(raw, sums, ["games"], opener=FakeNet(), sleep=lambda _: None)
    assert result[0].action == "downloaded"
    assert (raw / "steam_games.json.gz").read_bytes() == PAYLOAD


def test_fetch_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    sums = tmp_path / "checksums.txt"
    write_checksums(sums, {"steam_games.json.gz": "0" * 64})
    with pytest.raises(ChecksumMismatchError, match="differs"):
        fetch(tmp_path / "raw", sums, ["games"], opener=FakeNet(), sleep=lambda _: None)


def test_fetch_refuses_unrecorded_files_without_record(tmp_path: Path) -> None:
    with pytest.raises(ChecksumMissingError, match="--record"):
        fetch(tmp_path / "raw", tmp_path / "none.txt", ["games"], opener=FakeNet())


def test_fetch_rejects_unknown_source(tmp_path: Path) -> None:
    with pytest.raises(KeyError, match="unknown source"):
        fetch(tmp_path, tmp_path / "c.txt", ["nope"], record=True, opener=FakeNet())


def test_every_source_is_https_and_named_after_its_file() -> None:
    for source in SOURCES.values():
        assert source.url.startswith("https://")
        assert source.url.endswith("/" + source.filename)
    assert fetch_module.CHUNK == 1 << 20
