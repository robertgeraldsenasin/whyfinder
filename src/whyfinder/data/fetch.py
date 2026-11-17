"""Download the raw files with retries and verify them against recorded SHA-256 checksums (FR-01).

The network is injected (`opener`) and so is sleeping (`sleep`), so tests never touch the network
and never wait.
"""

from __future__ import annotations

import hashlib
import shutil
import time
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from whyfinder.data.sources import SOURCES, Source

Opener = Callable[[str, float], BinaryIO]
CHUNK = 1 << 20


class ChecksumMismatchError(RuntimeError):
    """A file's SHA-256 differs from the recorded one."""


class ChecksumMissingError(RuntimeError):
    """No checksum is recorded for a file and recording was not requested."""


class DownloadError(RuntimeError):
    """A download failed after every retry."""


@dataclass(frozen=True)
class FetchResult:
    """What happened to one file."""

    name: str
    path: Path
    sha256: str
    action: str  # "kept" (already present and verified), "downloaded" or "recorded"


def urlopen(url: str, timeout: float) -> BinaryIO:
    """Open a URL for streaming (the default opener)."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "whyfinder-data-fetch"})  # noqa: S310
    response: BinaryIO = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
    return response


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def read_checksums(path: Path) -> dict[str, str]:
    """Parse a `sha256sum`-style file: `<hex>  <filename>` per line; blank lines and # ignored."""
    if not path.exists():
        return {}
    checksums: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"{path}:{number}: expected '<sha256>  <filename>', got {raw!r}")
        checksums[parts[1]] = parts[0].lower()
    return checksums


def write_checksums(path: Path, checksums: dict[str, str]) -> None:
    """Write checksums sorted by filename, in `sha256sum` format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{digest}  {name}" for name, digest in sorted(checksums.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def download(
    url: str,
    dest: Path,
    *,
    opener: Opener = urlopen,
    retries: int = 4,
    backoff: float = 2.0,
    timeout: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Stream `url` to `dest` through a `.part` file; retry with exponential backoff."""
    if retries < 1:
        raise ValueError("retries must be at least 1")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with opener(url, timeout) as response, part.open("wb") as out:
                shutil.copyfileobj(response, out, CHUNK)
            part.replace(dest)
            return
        except OSError as error:  # URLError, HTTPError, timeouts and resets are all OSErrors
            last_error = error
            part.unlink(missing_ok=True)
            if attempt + 1 < retries:
                sleep(backoff * 2**attempt)
    raise DownloadError(f"{url}: failed after {retries} attempts: {last_error}") from last_error


def fetch(
    out_dir: Path,
    checksums_path: Path,
    names: Iterable[str],
    *,
    record: bool = False,
    opener: Opener = urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> list[FetchResult]:
    """Make sure every named file is in `out_dir` and matches its recorded checksum.

    A present file that verifies is kept. A missing or corrupt file is downloaded again. With
    `record=True`, files without a recorded checksum get one; otherwise they are an error, so a
    reproduction can never silently use different bytes.
    """
    checksums = read_checksums(checksums_path)
    results: list[FetchResult] = []
    for name in names:
        if name not in SOURCES:
            raise KeyError(f"unknown source {name!r}; known: {', '.join(sorted(SOURCES))}")
        source: Source = SOURCES[name]
        path = out_dir / source.filename
        expected = checksums.get(source.filename)
        if expected is None and not record:
            raise ChecksumMissingError(
                f"no checksum recorded for {source.filename} in {checksums_path}; "
                "run with --record once to record it"
            )
        if path.exists() and expected is not None and sha256_file(path) == expected:
            results.append(FetchResult(name, path, expected, "kept"))
            continue
        download(source.url, path, opener=opener, sleep=sleep)
        actual = sha256_file(path)
        if expected is None:
            checksums[source.filename] = actual
            write_checksums(checksums_path, checksums)
            results.append(FetchResult(name, path, actual, "recorded"))
        elif actual != expected:
            raise ChecksumMismatchError(
                f"{source.filename}: SHA-256 {actual} differs from the recorded {expected}"
            )
        else:
            results.append(FetchResult(name, path, actual, "downloaded"))
    return results
