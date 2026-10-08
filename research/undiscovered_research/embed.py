"""Vectors for each topic's sampled abstracts.

The main analysis uses ``tfidf``: word weights fitted, at each freeze, on
that freeze's own abstracts and nothing else. It cannot know anything
written after the freeze, which a pretrained model can: some embedding
models are trained on pairs of scientific papers, including citation pairs
from years after any freeze we test.

Any other name is a pretrained embedding model, used for robustness checks:
a local sentence-transformers model by default (free, no account), or any
OpenAI-compatible ``/embeddings`` endpoint when ``UNDISCOVERED_EMBED_URL``
(and optionally ``UNDISCOVERED_EMBED_KEY``) is set: Ollama, LM Studio, vLLM,
OpenRouter or a hosted provider. The project prescribes no model.

Vectors are L2-normalised. Pretrained ones are cached per (model, cutoff)
under ``research/data/emb/``; TF-IDF is fast enough to recompute.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import requests

from .collect import DATA

_local_models: dict[str, object] = {}

TFIDF = "tfidf"

# Which abstracts describe a topic (fixed in the plan, amended 2026-10-08).
# OpenAlex has placeholder "abstracts" ("International audience", "Ce texte
# est disponible en format PDF seulement", retraction notices) and many in
# other languages. Two topics that both publish in Portuguese would look
# alike to TF-IDF for a reason that has nothing to do with their content.
MIN_WORDS = 40              # title and abstract together
MIN_ENGLISH_SHARE = 0.25    # share of words that are common English words
MIN_ABSTRACTS = 5           # fewer usable abstracts: the topic has no content vector


def usable(text: str) -> bool:
    """An English text long enough to say what the paper is about."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < MIN_WORDS:
        return False
    return sum(w in ENGLISH_STOP_WORDS for w in words) / len(words) >= MIN_ENGLISH_SHARE


def usable_abstracts(abstracts: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Each topic's usable abstracts; topics with too few are left out."""
    out = {}
    for t, items in abstracts.items():
        kept = [a for a in items if usable(a["text"])]
        if len(kept) >= MIN_ABSTRACTS:
            out[t] = kept
    return out


# scikit-learn's English stop-word list also drops words that carry meaning
# in some field (thin films, wildfires, interest rates, systems biology); they
# are kept. Publisher and database boilerplate is dropped instead.
KEEP_WORDS = {"system", "thin", "thick", "fire", "bill", "mill", "interest", "found", "detail",
              "computer", "empty", "fill", "full", "front", "bottom", "top", "side", "part",
              "move", "describe", "show"}
BOILERPLATE = {"copyright", "elsevier", "springer", "wiley", "psycinfo", "apa", "ltd", "inc",
               "llc", "gmbh"}
_HEADING = re.compile(r"\b(?:background|objectives?|methods?|results|conclusions?|purpose|aims?|"
                      r"introduction|design|setting|participants|findings|keywords)\s*:", re.I)
_RIGHTS = re.compile(r"\u00a9|\(c\)|all rights reserved", re.I)


def stop_words() -> set[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    return (set(ENGLISH_STOP_WORDS) - KEEP_WORDS) | BOILERPLATE


def clean(text: str) -> str:
    """Remove section headings of structured abstracts and rights notices."""
    return _RIGHTS.sub(" ", _HEADING.sub(" ", text))


def _tfidf_topics(abstracts: dict[str, list[dict]]) -> dict[str, dict]:
    """TF-IDF over the abstracts given (one freeze's sample), and nothing else.

    Settings fixed in the plan: headings and rights notices removed, the stop
    words above, words of two or more letters only (no numbers), sublinear
    term frequency, terms kept if they appear in at least 2 abstracts and in
    at most half of them.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    owners, texts = [], []
    for t, items in abstracts.items():
        for a in items:
            owners.append(t)
            texts.append(clean(a["text"]))
    vec = TfidfVectorizer(stop_words=sorted(stop_words()), token_pattern=r"(?u)\b[^\W\d_]{2,}\b",
                          sublinear_tf=True, min_df=2, max_df=0.5)
    m = vec.fit_transform(texts).tocsr()          # rows are L2-normalised
    out = {}
    for t in abstracts:
        rows = [i for i, o in enumerate(owners) if o == t]
        if not rows:
            continue
        v = m[rows]
        c = np.asarray(v.mean(axis=0)).ravel().astype(np.float32)
        out[t] = {"vecs": v, "centroid": c / max(float(np.linalg.norm(c)), 1e-12)}
    return out


def _embed_local(model: str, texts: list[str]) -> np.ndarray:
    try:
        import torch
        from sentence_transformers import SentenceTransformer  # imported only when used
    except ImportError as e:
        raise SystemExit("Pretrained embeddings need the optional packages: "
                         "pip install -r research/requirements-embeddings.txt") from e
    from .gentle import THREADS
    torch.set_num_threads(THREADS)
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
    """{topic: {"vecs": (n, d) unit vectors, "centroid": (d,) unit vector}}.

    Only usable abstracts count (see ``usable``), and a topic with fewer than
    ``MIN_ABSTRACTS`` of them gets no vector, so its pairs drop out for every
    model alike. For ``tfidf`` the vectors are a sparse matrix; everything
    else is dense.
    """
    abstracts = usable_abstracts(abstracts)
    if model == TFIDF:
        return _tfidf_topics(abstracts)
    cache = DATA / "emb" / "usable-clean" / model.replace("/", "_") / f"{cutoff}.npz"
    stored: dict[str, np.ndarray] = {}
    if cache.exists():
        with np.load(cache) as z:
            stored = {k: z[k] for k in z.files}
    todo = [t for t in abstracts if t not in stored and abstracts[t]]
    if todo:
        texts, owner = [], []
        for t in todo:
            for a in abstracts[t]:
                texts.append(clean(a["text"])[:4000])
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
