"""A small, polite, cached client for the OpenAlex API.

OpenAlex is free. Without a key each IP address gets a small shared daily
budget (about 1,000 list queries); a free key from
https://openalex.org/settings/api raises that to $1 a day, about 10,000
list queries. Set it as ``OPENALEX_API_KEY`` or put it in
``research/.openalex_key`` (git-ignored). The key travels in a header, never
in the URL, so it never reaches the cache or a log.

This client keeps to a few requests a second, retries server errors with
backoff, stops cleanly when the daily budget is spent (instead of retrying
for hours), and caches every response under ``research/cache/`` so a rerun
costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

import requests

API = "https://api.openalex.org"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
MIN_INTERVAL = 0.2  # seconds between live requests: 5 a second
_last_request = 0.0
_session = requests.Session()
_session.headers["User-Agent"] = "undiscovered-research (https://github.com/nicolas-maman/undiscovered)"
_KEY_FILE = Path(__file__).resolve().parent.parent / ".openalex_key"
_key = os.environ.get("OPENALEX_API_KEY") or (
    _KEY_FILE.read_text(encoding="utf-8").strip() if _KEY_FILE.exists() else "")
if _key:
    _session.headers["Authorization"] = f"Bearer {_key}"


class BudgetExhausted(RuntimeError):
    """The daily OpenAlex budget is spent; it resets at midnight UTC."""


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / digest[:2] / f"{digest}.json"


def get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET ``API/path`` with ``params``; cached, rate-limited, retried."""
    global _last_request
    req = requests.Request("GET", f"{API}/{path}", params=params).prepare()
    url = req.url or ""
    cached = _cache_path(url)
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))

    delay = 1.0
    for attempt in range(8):
        wait = MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            resp = _session.get(url, timeout=90)
        except requests.RequestException:
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        if resp.status_code == 200:
            data = resp.json()
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(data), encoding="utf-8")
            return data
        if resp.status_code == 429 and "budget" in resp.text.lower():
            try:
                reset = int(resp.json().get("retryAfter", 0))
            except ValueError:
                reset = 0
            raise BudgetExhausted(
                f"OpenAlex daily budget spent ({'with' if _key else 'without'} a key); "
                f"resets in {reset // 3600}h{(reset % 3600) // 60:02d}m. "
                + ("" if _key else "A free key raises it tenfold: https://openalex.org/settings/api"))
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        raise RuntimeError(f"OpenAlex {resp.status_code} for {url}: {resp.text[:300]}")
    raise RuntimeError(f"OpenAlex: gave up after retries: {url}")


def paged(path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every page of a cursor-paged list or group_by, as raw responses."""
    cursor = "*"
    per_page = int(params.get("per_page", 25))
    while cursor:
        page = get(path, {**params, "cursor": cursor})
        yield page
        # A short page is the last one. Without this check the cursor runs on
        # for one more, empty, page, which costs a request every time.
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
    slots: dict[int, str] = {}
    for word, positions in inverted.items():
        for p in positions:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))
