"""The volunteer's AI model, whichever it is.

Three kinds of endpoint cover nearly every model:

    openai-compatible   Ollama, LM Studio, llama.cpp's server, vLLM, OpenRouter, Groq, OpenAI...
    anthropic           Anthropic's API
    google              Google's Gemini API

The project prescribes no model and pays for none. A key, if the endpoint
needs one, comes from the settings file or UNDISCOVERED_MODEL_KEY, is sent
only to that endpoint, and is never printed or submitted. Every question is
asked at temperature 0.
"""

from __future__ import annotations

import os
import time

import requests

from . import __version__

KINDS = ("openai-compatible", "anthropic", "google")
BASE = {"anthropic": "https://api.anthropic.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta"}
LOCAL = {"Ollama": "http://127.0.0.1:11434/v1", "LM Studio": "http://127.0.0.1:1234/v1"}
MAX_TOKENS = 2048       # room for models that think before they answer


class ModelError(RuntimeError):
    """The model could not be reached or answered something unusable."""


class Model:
    def __init__(self, provider: str, model_id: str, base_url: str = "", key: str = "",
                 timeout: float = 600):
        if provider not in KINDS:
            raise ModelError(f"unknown provider {provider!r}; use one of {', '.join(KINDS)}")
        if not model_id:
            raise ModelError("no model chosen; run: undiscovered setup")
        self.provider, self.id, self.key, self.timeout = provider, model_id, key, timeout
        self.base = (base_url or BASE.get(provider, "")).rstrip("/")
        if not self.base:
            raise ModelError("an openai-compatible model needs its base URL, such as " + LOCAL["Ollama"])
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
        """The model's answer as text. Retries when the endpoint is busy or briefly unreachable."""
        url, headers, body = self._request(system, user)
        delay = 2.0
        for attempt in range(6):
            try:
                resp = self._session.post(url, headers=headers, json=body, timeout=self.timeout)
            except requests.RequestException as e:
                if attempt == 5:
                    raise ModelError(f"cannot reach the model at {self.base} ({type(e).__name__})") from None
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            if resp.status_code == 200:
                return self._text(resp.json())
            if resp.status_code in (429, 500, 502, 503, 504, 529) and attempt < 5:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise ModelError(f"the model at {self.base} answered {resp.status_code}: {resp.text[:300]}")
        raise ModelError(f"the model at {self.base} kept failing")


def key(cfg: dict) -> str:
    return os.environ.get("UNDISCOVERED_MODEL_KEY") or cfg.get("model", {}).get("key", "")


def from_settings(cfg: dict) -> Model | None:
    """The volunteer's model from their settings, or None when they have not chosen one."""
    m = cfg.get("model") or {}
    if not m.get("id"):
        return None
    return Model(m.get("provider", "openai-compatible"), m["id"], m.get("base_url", ""), key(cfg))


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
