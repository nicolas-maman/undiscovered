"""Embeddings for each topic's sampled abstracts, from any provider.

The research run uses a local sentence-transformers model, so it is free
and needs no account. Setting ``UNDISCOVERED_EMBED_URL`` (and optionally
``UNDISCOVERED_EMBED_KEY``) switches to any OpenAI-compatible
``/embeddings`` endpoint instead: Ollama, LM Studio, vLLM, OpenRouter or a
hosted provider. The project prescribes no model.

Vectors are L2-normalised and cached per (model, cutoff) under
``research/data/emb/``.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import requests

from .collect import DATA

_local_models: dict[str, object] = {}


def _embed_local(model: str, texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer  # imported only when used
    if model not in _local_models:
        _local_models[model] = SentenceTransformer(model)
    st = _local_models[model]
    return np.asarray(st.encode(texts, batch_size=32, normalize_embeddings=True,
                                show_progress_bar=False), dtype=np.float32)


def _embed_remote(model: str, texts: list[str]) -> np.ndarray:
    url = os.environ["UNDISCOVERED_EMBED_URL"].rstrip("/") + "/embeddings"
    headers = {}
    if os.environ.get("UNDISCOVERED_EMBED_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['UNDISCOVERED_EMBED_KEY']}"
    out = []
    for i in range(0, len(texts), 64):
        resp = requests.post(url, json={"model": model, "input": texts[i:i + 64]},
                             headers=headers, timeout=300)
        resp.raise_for_status()
        out.extend(d["embedding"] for d in sorted(resp.json()["data"], key=lambda d: d["index"]))
    v = np.asarray(out, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def embed(model: str, texts: list[str]) -> np.ndarray:
    if os.environ.get("UNDISCOVERED_EMBED_URL"):
        return _embed_remote(model, texts)
    return _embed_local(model, texts)


def topic_embeddings(cutoff: int, model: str,
                     abstracts: dict[str, list[dict]]) -> dict[str, dict]:
    """{topic: {"vecs": (n, d) unit vectors, "centroid": (d,) unit vector}}."""
    cache = DATA / "emb" / model.replace("/", "_") / f"{cutoff}.npz"
    stored: dict[str, np.ndarray] = {}
    if cache.exists():
        with np.load(cache) as z:
            stored = {k: z[k] for k in z.files}
    todo = [t for t in abstracts if t not in stored and abstracts[t]]
    if todo:
        texts, owner = [], []
        for t in todo:
            for a in abstracts[t]:
                texts.append(a["text"][:4000])
                owner.append(t)
        vecs = embed(model, texts)
        for t in todo:
            stored[t] = vecs[[i for i, o in enumerate(owner) if o == t]]
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **stored)
    out = {}
    for t, v in stored.items():
        if t not in abstracts or len(v) == 0:
            continue
        c = v.mean(axis=0)
        out[t] = {"vecs": v, "centroid": c / max(float(np.linalg.norm(c)), 1e-12)}
    return out
