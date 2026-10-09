"""A small OpenAlex client for one unit of work.

It keeps to a few requests a second, retries server errors, stops cleanly
when the volunteer's daily allowance is spent, and caches responses in a
folder that is deleted when the unit is done. The OpenAlex key, if any, is
sent only to OpenAlex, and never written to the cache or printed.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import zlib
from pathlib import Path
from typing import Any, Iterator

import requests

from . import __version__

API = "https://api.openalex.org"
MIN_INTERVAL = 0.2          # seconds between live requests: 5 a second


class BudgetExhausted(RuntimeError):
    """The day's OpenAlex allowance is spent; it resets at midnight UTC."""


class OpenAlex:
    def __init__(self, cache_dir: Path, key: str = ""):
        self.cache_dir = cache_dir
        self.key = key
        self.remaining: int | None = None
        self._last = 0.0
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            f"undiscovered-py/{__version__} (https://github.com/nicolas-maman/undiscovered)")

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / digest[:2] / f"{digest}.json.gz"

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = requests.Request("GET", f"{API}/{path}", params=params).prepare().url or ""
        cached = self._path(url)           # the key is not part of it
        if cached.exists():
            try:
                return json.loads(gzip.decompress(cached.read_bytes()).decode("utf-8"))
            except (OSError, EOFError, ValueError, zlib.error):
                cached.unlink(missing_ok=True)
        send = {**params, "api_key": self.key} if self.key else params
        delay = 1.0
        for _ in range(8):
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self._session.get(f"{API}/{path}", params=send, timeout=90)
            except requests.RequestException:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            if resp.headers.get("X-RateLimit-Remaining", "").isdigit():
                self.remaining = int(resp.headers["X-RateLimit-Remaining"])
            if resp.status_code == 200:
                data = resp.json()
                cached.parent.mkdir(parents=True, exist_ok=True)
                tmp = cached.with_name(cached.name + ".tmp")
                tmp.write_bytes(gzip.compress(json.dumps(data).encode("utf-8")))
                os.replace(tmp, cached)
                return data
            if resp.status_code == 429 and "budget" in resp.text.lower():
                raise BudgetExhausted("your OpenAlex allowance for today is spent; it resets at "
                                      "midnight UTC" + ("" if self.key else
                                      ". A free key gives ten times more: https://openalex.org/settings/api"))
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"OpenAlex answered {resp.status_code} for {url}")
        raise RuntimeError(f"OpenAlex: gave up after retries: {url}")

    def paged(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Every page of a cursor-paged list or group_by. A short page is the last one."""
        cursor = "*"
        per_page = int(params.get("per_page", 25))
        while cursor:
            page = self.get(path, {**params, "cursor": cursor})
            yield page
            items = page.get("group_by") if "group_by" in params else page.get("results")
            if len(items or []) < per_page:
                break
            cursor = page.get("meta", {}).get("next_cursor")


def short_id(openalex_id: str) -> str:
    """``https://openalex.org/T10005`` -> ``T10005``."""
    return openalex_id.rsplit("/", 1)[-1]


def abstract_text(inverted: dict[str, list[int]] | None) -> str:
    """Rebuild an abstract from OpenAlex's inverted index."""
    if not inverted:
        return ""
    slots = {p: word for word, positions in inverted.items() for p in positions}
    return " ".join(slots[i] for i in sorted(slots))
