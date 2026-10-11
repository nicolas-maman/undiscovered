"""Combine the describing results: agreement between models, paper twins, and the open index.

    pip install numpy scikit-learn       # this script only
    python pipeline/combine.py <distill-2025 checkout>

Reads results/<unit>/<issue>.json and papers.json and writes combined/:

    descriptions.jsonl   every accepted description, one paper per line: the open index (CC0)
    models.json          for each model: what it described, and how well its descriptions agree
                         with other volunteers' descriptions of the same papers, against chance
    twins.json           pairs of papers from different domains whose descriptions are most alike

Similarity is the cosine between TF-IDF vectors of a description's problem
and approach (English stop words removed, sublinear term frequency, words in
at least two descriptions). It is simple and anyone can recompute it;
whether a learned embedding finds better twins is a question for the data
once there is enough of it.

Agreement is measured only between descriptions of the same paper by two
different volunteers using two different models: at temperature 0 one model
tends to write the same thing twice, which says nothing about whether it is
right. Chance is the similarity between descriptions of two different
papers, from a fixed random sample of such pairs. A paper counts as reliably
described when two different models' descriptions of it agree more than 95%
of chance pairs do; only those papers are paired into twins, so a vague
description, which looks like many papers, cannot make a twin.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

SEED = 2025
CHANCE_PAIRS = 20000        # pairs of descriptions of different papers, for the chance level
RELIABLE = 95               # percentile of chance a paper's two descriptions must beat
TWINS = 50                  # pairs published
PER_PAPER = 2               # times one paper may appear among them
MIN_DESCRIPTIONS = 40       # below this there is too little to compare


def load(branch: Path) -> tuple[dict, list[dict]]:
    papers = json.loads((branch / "papers.json").read_text(encoding="utf-8"))
    rows = []
    for f in sorted((branch / "results").glob("*/*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        for d in r["descriptions"]:
            rows.append({"work": d["work"], "author": r["author"], "model": (r["model"]["provider"], r["model"]["id"]),
                         "problem": d["problem"], "approach": d["approach"]})
    return papers, rows


def vectors(rows: list[dict]):
    texts = [f"{r['problem']} {r['approach']}" for r in rows]
    return TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2).fit_transform(texts)


def chance(X, rows: list[dict], rng: np.random.Generator, n: int = CHANCE_PAIRS) -> np.ndarray:
    """Similarities of descriptions of two different papers, from a fixed random sample."""
    i, j = rng.integers(0, len(rows), n), rng.integers(0, len(rows), n)
    keep = np.array([rows[a]["work"] != rows[b]["work"] for a, b in zip(i, j)])
    i, j = i[keep], j[keep]
    return np.asarray(X[i].multiply(X[j]).sum(axis=1)).ravel()


def same_paper_pairs(rows: list[dict]) -> list[tuple[int, int]]:
    """Pairs of descriptions of the same paper by two different volunteers with two different models."""
    by_work = defaultdict(list)
    for k, r in enumerate(rows):
        by_work[r["work"]].append(k)
    return [(a, b) for ks in by_work.values() for x, a in enumerate(ks) for b in ks[x + 1:]
            if rows[a]["author"] != rows[b]["author"] and rows[a]["model"] != rows[b]["model"]]


def models(X, rows: list[dict], pairs: list[tuple[int, int]], rng: np.random.Generator) -> list[dict]:
    agree, described, papers = defaultdict(list), defaultdict(int), defaultdict(set)
    for r in rows:
        described[r["model"]] += 1
        papers[r["model"]].add(r["work"])
    for a, b in pairs:
        s = float(X[a].multiply(X[b]).sum())
        agree[rows[a]["model"]].append(s)
        agree[rows[b]["model"]].append(s)
    out = []
    for m in sorted(described, key=lambda m: (-described[m], m)):
        own = [k for k, r in enumerate(rows) if r["model"] == m]
        other = rng.integers(0, len(rows), len(own))
        sims = [float(X[k].multiply(X[o]).sum()) for k, o in zip(own, other) if rows[k]["work"] != rows[o]["work"]]
        out.append({"provider": m[0], "id": m[1], "descriptions": described[m], "papers": len(papers[m]),
                    "pairs": len(agree[m]),
                    "agreement": round(float(np.mean(agree[m])), 4) if agree[m] else None,
                    "chance": round(float(np.mean(sims)), 4) if sims else None})
    return out


def twins(X, rows: list[dict], pairs: list[tuple[int, int]], papers: dict, threshold: float) -> list[dict]:
    """The most alike pairs of reliably described papers from different domains."""
    agree = defaultdict(list)
    for a, b in pairs:
        agree[rows[a]["work"]].append(float(X[a].multiply(X[b]).sum()))
    reliable = sorted(w for w, s in agree.items() if np.mean(s) > threshold)
    if len(reliable) < 2:
        return []
    by_work = defaultdict(list)
    for k, r in enumerate(rows):
        by_work[r["work"]].append(k)
    V = np.vstack([np.asarray(X[by_work[w]].mean(axis=0)).ravel() for w in reliable])
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    S = V @ V.T
    domain = np.array([papers[w]["domain"] for w in reliable])
    S[domain[:, None] == domain[None, :]] = -1          # same domain: not a twin
    iu = np.triu_indices(len(reliable), 1)
    order = np.argsort(-S[iu], kind="stable")
    used, out = defaultdict(int), []
    for k in order:
        a, b = iu[0][k], iu[1][k]
        if S[a, b] <= 0 or len(out) >= TWINS:
            break
        wa, wb = reliable[a], reliable[b]
        if used[wa] >= PER_PAPER or used[wb] >= PER_PAPER:
            continue
        used[wa] += 1
        used[wb] += 1
        side = lambda w: {"work": w, **papers[w],  # noqa: E731
                          "descriptions": [{"problem": rows[i]["problem"], "approach": rows[i]["approach"],
                                            "model": rows[i]["model"][1]} for i in by_work[w]]}
        out.append({"similarity": round(float(S[a, b]), 4), "a": side(wa), "b": side(wb)})
    return out


def combine(branch: Path) -> dict:
    papers, rows = load(branch)
    out_dir = branch / "combined"
    out_dir.mkdir(exist_ok=True)
    by_work = defaultdict(list)
    for r in rows:
        by_work[r["work"]].append({"problem": r["problem"], "approach": r["approach"], "author": r["author"],
                                   "model": {"provider": r["model"][0], "id": r["model"][1]}})
    with (out_dir / "descriptions.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for w in sorted(by_work):
            f.write(json.dumps({"work": w, **papers.get(w, {}), "descriptions": by_work[w]}, ensure_ascii=False) + "\n")
    summary = {"descriptions": len(rows), "papers": len(by_work), "method": "tf-idf cosine",
               "reliable_percentile": RELIABLE, "models": [], "twins": []}
    if len(rows) >= MIN_DESCRIPTIONS:
        rng = np.random.default_rng(SEED)
        X = vectors(rows)
        base = chance(X, rows, rng)
        pairs = same_paper_pairs(rows)
        threshold = float(np.percentile(base, RELIABLE))
        summary.update(chance_median=round(float(np.median(base)), 4), reliable_above=round(threshold, 4),
                       models=models(X, rows, pairs, rng), twins=twins(X, rows, pairs, papers, threshold))
    else:
        summary["note"] = f"Fewer than {MIN_DESCRIPTIONS} descriptions so far: nothing to compare yet."
    twins_out = summary.pop("twins")
    (out_dir / "models.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "twins.json").write_text(json.dumps({"method": summary["method"], "twins": twins_out},
                                                   indent=1, ensure_ascii=False), encoding="utf-8")
    return {**summary, "twins": len(twins_out)}


if __name__ == "__main__":
    print(json.dumps(combine(Path(sys.argv[1])), indent=1)[:2000])
