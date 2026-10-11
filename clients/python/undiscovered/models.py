"""The volunteer's AI model, whichever it is.

Three kinds of endpoint cover nearly every model:

    openai-compatible   Ollama, LM Studio, llama.cpp, vLLM, Jan, GitHub Models, Groq, OpenRouter,
                        Mistral, OpenAI, Google's compatibility endpoint, and many more
    anthropic           Anthropic's API
    google              Google's Gemini API

The project prescribes no model and pays for none. Settings come from the
settings file, and each can be overridden by an environment variable, so the
client also runs in a notebook or a script with no setup:

    UNDISCOVERED_MODEL_PROVIDER   openai-compatible (the default), anthropic or google
    UNDISCOVERED_MODEL_BASE_URL   the server's address, such as http://127.0.0.1:11434/v1
    UNDISCOVERED_MODEL            the model's name, as the server writes it
    UNDISCOVERED_MODEL_KEY        the key, if the server needs one

The key is sent only to that server and is never printed or submitted.
Every question is asked at temperature 0. Free tiers limit how fast one may
ask; rather than guess each provider's limits, the client waits as long as
the server says (Retry-After) and slows down whenever it is told it is
asking too fast.
"""

from __future__ import annotations

import email.utils
import os
import time

import requests

from . import __version__

KINDS = ("openai-compatible", "anthropic", "google")
BASE = {"anthropic": "https://api.anthropic.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta"}
LOCAL = {"Ollama": "http://127.0.0.1:11434/v1", "LM Studio": "http://127.0.0.1:1234/v1",
         "llama.cpp": "http://127.0.0.1:8080/v1", "vLLM": "http://127.0.0.1:8000/v1",
         "Jan": "http://127.0.0.1:1337/v1"}
# Services `undiscovered setup` offers by name: (name, kind, base URL, where to get a key, what it costs).
PRESETS = [
    ("GitHub Models", "openai-compatible", "https://models.github.ai/inference",
     "a GitHub token with the Models: read permission (github.com/settings/tokens)",
     "free with a GitHub account, within rate limits"),
    ("Google Gemini", "google", "", "aistudio.google.com/apikey", "free tier, within rate limits"),
    ("Groq", "openai-compatible", "https://api.groq.com/openai/v1", "console.groq.com/keys",
     "free tier, within rate limits"),
    ("OpenRouter", "openai-compatible", "https://openrouter.ai/api/v1", "openrouter.ai/keys",
     "models whose name ends in :free cost nothing, a small number a day"),
    ("Mistral", "openai-compatible", "https://api.mistral.ai/v1", "console.mistral.ai",
     "free Experiment plan; Mistral may train on what it is sent"),
    ("OpenAI", "openai-compatible", "https://api.openai.com/v1", "platform.openai.com/api-keys", "paid"),
    ("Anthropic", "anthropic", "", "console.anthropic.com", "paid"),
]
MAX_TOKENS = 2048       # room for models that think before they answer
SLOWEST = 30.0          # the longest the client will wait between questions of its own accord


class ModelError(RuntimeError):
    """The model could not be reached or answered something unusable."""


def retry_after(resp: requests.Response) -> float | None:
    """Seconds the server asks us to wait, from its Retry-After header, if it gave one."""
    value = resp.headers.get("Retry-After", "").strip()
    if not value:
        return None
    if value.replace(".", "", 1).isdigit():
        return float(value)
    when = email.utils.parsedate_to_datetime(value) if value else None
    return max(0.0, when.timestamp() - time.time()) if when else None


class Model:
    def __init__(self, provider: str, model_id: str, base_url: str = "", key: str = "",
                 timeout: float = 600, interval: float = 0.0):
        if provider not in KINDS:
            raise ModelError(f"unknown provider {provider!r}; use one of {', '.join(KINDS)}")
        if not model_id:
            raise ModelError("no model chosen; run: undiscovered setup")
        self.provider, self.id, self.key, self.timeout = provider, model_id, key, timeout
        self.base = (base_url or BASE.get(provider, "")).rstrip("/")
        if not self.base:
            raise ModelError("an openai-compatible model needs its base URL, such as " + LOCAL["Ollama"])
        self.interval = interval        # seconds between questions; grows when the server says to slow down
        self._last = 0.0
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            f"undiscovered-py/{__version__} (https://github.com/nicolas-maman/undiscovered)")

    @property
    def provenance(self) -> dict:
        """What every result records about the model that produced it."""
        return {"provider": self.provider, "id": self.id}

    def _request(self, system: str, user: str) -> tuple[str, dict, dict]:
        if self.provider == "anthropic":
            return (f"{self.base}/messages",
                    {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                    {"model": self.id, "max_tokens": MAX_TOKENS, "temperature": 0, "system": system,
                     "messages": [{"role": "user", "content": user}]})
        if self.provider == "google":
            return (f"{self.base}/models/{self.id}:generateContent",
                    {"x-goog-api-key": self.key},
                    {"systemInstruction": {"parts": [{"text": system}]},
                     "contents": [{"role": "user", "parts": [{"text": user}]}],
                     "generationConfig": {"temperature": 0, "maxOutputTokens": MAX_TOKENS}})
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        return (f"{self.base}/chat/completions", headers,
                {"model": self.id, "temperature": 0, "max_tokens": MAX_TOKENS,
                 "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})

    def _text(self, data: dict) -> str:
        try:
            if self.provider == "anthropic":
                return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
            if self.provider == "google":
                return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ModelError(f"{self.provider} answered in an unexpected shape") from None

    def ask(self, system: str, user: str) -> str:
        """The model's answer as text, waiting and retrying when the server is busy or limits the pace."""
        url, headers, body = self._request(system, user)
        delay = 2.0
        for attempt in range(8):
            wait = self.interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self._session.post(url, headers=headers, json=body, timeout=self.timeout)
            except requests.RequestException as e:
                if attempt == 7:
                    raise ModelError(f"cannot reach the model at {self.base} ({type(e).__name__})") from None
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            if resp.status_code == 200:
                return self._text(resp.json())
            if resp.status_code == 429:         # asked too fast: wait as told, and ask more slowly from now on
                self.interval = min(SLOWEST, max(2.0, self.interval * 2))
                time.sleep(retry_after(resp) or delay)
                delay = min(delay * 2, 120)
                continue
            if resp.status_code in (500, 502, 503, 504, 529) and attempt < 7:
                time.sleep(retry_after(resp) or delay)
                delay = min(delay * 2, 60)
                continue
            raise ModelError(f"the model at {self.base} answered {resp.status_code}: {resp.text[:300]}")
        raise ModelError(f"the model at {self.base} kept saying it is busy or that we ask too often; "
                         "if it has a daily limit, it may be reached, so try again later")


def settings(cfg: dict) -> dict:
    """The model settings: the settings file, with any environment variable taking precedence."""
    m = dict(cfg.get("model") or {})
    for field, var in (("provider", "UNDISCOVERED_MODEL_PROVIDER"), ("base_url", "UNDISCOVERED_MODEL_BASE_URL"),
                       ("id", "UNDISCOVERED_MODEL"), ("key", "UNDISCOVERED_MODEL_KEY")):
        if os.environ.get(var):
            m[field] = os.environ[var]
    return m


def key(cfg: dict) -> str:
    return settings(cfg).get("key", "")


def from_settings(cfg: dict) -> Model | None:
    """The volunteer's model, or None when they have not chosen one."""
    m = settings(cfg)
    if not m.get("id"):
        return None
    return Model(m.get("provider") or "openai-compatible", m["id"], m.get("base_url", ""), m.get("key", ""),
                 interval=float(m.get("interval", 0) or 0))


def local_models(timeout: float = 2.0) -> list[tuple[str, str, str]]:
    """(server name, base URL, model id) for every model a local server on this machine offers."""
    found = []
    for name, base in LOCAL.items():
        try:
            data = requests.get(f"{base}/models", timeout=timeout).json()
        except (requests.RequestException, ValueError):
            continue
        for m in data.get("data", []) if isinstance(data, dict) else []:
            if isinstance(m, dict) and m.get("id"):
                found.append((name, base, m["id"]))
    return found
