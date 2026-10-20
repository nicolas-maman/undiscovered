"""Combine the describing results: agreement between models, paper twins, and the open index.

    pip install numpy scikit-learn       # this script only
    python pipeline/combine.py <distill-2025 checkout>

Reads results/<unit>/<issue>.json, papers.json and, when it is there,
abstracts.jsonl (for titles), and writes combined/:

    descriptions.jsonl   every accepted description, one paper per line: the open index (CC0)
    models.json          for each model: what it described, and how well its descriptions agree
                         with other models' descriptions of the same papers, against chance
    twins.json           pairs of papers from different fields whose descriptions are most alike,
                         each with the words that made them alike
    neighbours.json      for every described paper, the papers from other fields most like it

Similarity is the cosine between TF-IDF vectors of a description's problem
and approach (English stop words removed, sublinear term frequency, words in
at least two descriptions). A paper's vector is the mean of its descriptions'.
It is simple and anyone can recompute it; whether a learned embedding finds
better twins is a question for the data once there is enough of it.

Agreement is measured only between descriptions of the same paper by two
different models: at temperature 0 one model tends to write the same thing
twice, which says nothing about whether it is right. Chance is the
similarity between descriptions of two different papers, from a fixed random
sample of such pairs.

A paper is reliably described when two different models' descriptions of it
agree more than 95% of chance pairs do, and more than its descriptions are
like 99% of the other papers' descriptions. The second condition stops
boilerplate: two models that write the same generic words for every paper
agree with each other, but they agree just as much with every other paper.

Twins come in two kinds. "Two models agree" pairs join reliably described
papers. "One model so far" pairs join papers that only one model has
described yet, or whose models do not yet agree; they are leads, published
so that the first volunteers see what their work finds, and the site says
which kind each pair is. Papers whose descriptions are among the 5% most
like everything else are never paired. Pairs within one field (OpenAlex's
26 fields, or a benchmark paper's own field) are left out, and so is a pair
of two benchmark papers of the same family, which is a known case recovered
rather than a lead; those are listed apart, as a check that the method finds
what is already known.
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
RELIABLE = 95               # percentile of chance a paper's two models' descriptions must beat
DISTINCT = 99               # percentile of a paper's likeness to other papers its own agreement must beat
GENERIC = 95                # papers above this percentile of mean likeness to all others are never paired
TWINS = 50                  # pairs published, of each kind
PER_PAPER = 2               # times one paper may appear among them
NEIGHBOURS = 5              # nearest papers from other fields kept for each paper
WHY = 6                     # shared words shown for a pair
MIN_DESCRIPTIONS = 40       # below this there is too little to compare
BINS = 20                   # histogram bins on [0, 1] for the site


def load(branch: Path) -> tuple[dict, list[dict]]:
    papers = json.loads((branch / "papers.json").read_text(encoding="utf-8"))
    twins = branch / "known-twins.json"
    if twins.exists():                  # the benchmark's families, so a recovered known case is not a lead
        for p in json.loads(twins.read_text(encoding="utf-8"))["papers"]:
            if p["work"] in papers:
                papers[p["work"]] = {**papers[p["work"]], "family": p["family"], "role": p["role"]}
    abstracts = branch / "abstracts.jsonl"
    if abstracts.exists():
        for line in abstracts.read_text(encoding="utf-8").splitlines():
            a = json.loads(line)
            if a["work"] in papers:
                papers[a["work"]] = {**papers[a["work"]], "title": a.get("title", ""), "year": a.get("year")}
    rows = []
    for f in sorted((branch / "results").glob("*/*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        for d in r["descriptions"]:
            rows.append({"work": d["work"], "author": r["author"], "model": (r["model"]["provider"], r["model"]["id"]),
                         "problem": d["problem"], "approach": d["approach"]})
    return papers, rows


def vectors(rows: list[dict]):
    texts = [f"{r['problem']} {r['approach']}" for r in rows]
    tfidf = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2)
    return tfidf.fit_transform(texts), tfidf.get_feature_names_out()


def chance(X, rows: list[dict], rng: np.random.Generator, n: int = CHANCE_PAIRS) -> np.ndarray:
    """Similarities of descriptions of two different papers, from a fixed random sample."""
    i, j = rng.integers(0, len(rows), n), rng.integers(0, len(rows), n)
    keep = np.array([rows[a]["work"] != rows[b]["work"] for a, b in zip(i, j)])
    i, j = i[keep], j[keep]
    return np.asarray(X[i].multiply(X[j]).sum(axis=1)).ravel()


def same_paper_pairs(rows: list[dict]) -> list[tuple[int, int]]:
    """Pairs of descriptions of the same paper by two different models."""
    by_work = defaultdict(list)
    for k, r in enumerate(rows):
        by_work[r["work"]].append(k)
    return [(a, b) for ks in by_work.values() for x, a in enumerate(ks) for b in ks[x + 1:]
            if rows[a]["model"] != rows[b]["model"]]


def histogram(values) -> list[int]:
    counts, _ = np.histogram(np.clip(np.asarray(values, dtype=float), 0, 1), bins=BINS, range=(0, 1))
    return counts.tolist()


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
                    "chance": round(float(np.mean(sims)), 4) if sims else None,
                    "agreement_histogram": histogram(agree[m]), "chance_histogram": histogram(sims)})
    return out


def paper_vectors(X, rows: list[dict]) -> tuple[list[str], np.ndarray, dict[str, list[int]]]:
    """Every described paper, its unit-length mean vector, and the rows that describe it."""
    by_work = defaultdict(list)
    for k, r in enumerate(rows):
        by_work[r["work"]].append(k)
    works = sorted(by_work)
    V = np.vstack([np.asarray(X[by_work[w]].mean(axis=0)).ravel() for w in works]).astype(np.float32)
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    return works, V, by_work


def field_of(paper: dict, work: str) -> str:
    """The field a pair must cross: OpenAlex's field, a benchmark paper's own, or the paper alone."""
    return paper.get("field") or paper.get("domain") or work


def reliable_papers(X, rows, pairs, works, V, threshold: float) -> dict[str, float]:
    """Papers whose models agree beyond chance and beyond the paper's likeness to other papers."""
    agree = defaultdict(list)
    for a, b in pairs:
        agree[rows[a]["work"]].append(float(X[a].multiply(X[b]).sum()))
    index = {w: i for i, w in enumerate(works)}
    out = {}
    for w, sims in agree.items():
        mine = float(np.mean(sims))
        if mine <= threshold:
            continue
        others = V @ V[index[w]]
        others = np.delete(others, index[w])
        if others.size == 0 or mine > float(np.percentile(others, DISTINCT)):
            out[w] = mine
    return out


def why(X_terms: np.ndarray, a: np.ndarray, b: np.ndarray) -> list[list]:
    """The words that make two papers alike: those with the largest share of their cosine."""
    share = a * b
    top = np.argsort(-share)[:WHY]
    return [[str(X_terms[i]), round(float(share[i]), 4)] for i in top if share[i] > 0]


CANDIDATES = 40             # each paper's most alike papers considered when choosing twins


def candidates(S: np.ndarray) -> list[tuple[float, int, int]]:
    """Each paper's CANDIDATES most alike papers, as (similarity, a, b) with a < b, most alike first.

    The most alike pairs overall are always among some paper's most alike, so
    this finds them without sorting every pair of papers.
    """
    k = min(CANDIDATES, S.shape[0] - 1)
    if k < 1:
        return []
    top = np.argpartition(-S, k - 1, axis=1)[:, :k]
    found = {}
    for a in range(S.shape[0]):
        for b in top[a]:
            b = int(b)
            if S[a, b] > 0:
                found[(min(a, b), max(a, b))] = float(S[a, b])
    return sorted(((s, a, b) for (a, b), s in found.items()), key=lambda t: (-t[0], t[1], t[2]))


def similar_pairs(ranked: list, works: list[str], allowed, used: dict, limit: int) -> list[tuple[int, int, float]]:
    """The most alike allowed pairs, each paper at most PER_PAPER times."""
    out = []
    for s, a, b in ranked:
        if len(out) >= limit:
            break
        wa, wb = works[a], works[b]
        if not allowed(a, b) or used[wa] >= PER_PAPER or used[wb] >= PER_PAPER:
            continue
        used[wa] += 1
        used[wb] += 1
        out.append((a, b, s))
    return out


def pairing(X, terms, rows, pairs, papers, threshold) -> tuple[dict, dict]:
    """Twins of both kinds, known cases recovered, and every paper's neighbours from other fields."""
    works, V, by_work = paper_vectors(X, rows)
    reliable = reliable_papers(X, rows, pairs, works, V, threshold)
    S = V @ V.T
    np.fill_diagonal(S, -1)
    n = len(works)
    mean_like = (S.sum(axis=1) + 1) / max(n - 1, 1)
    generic = mean_like > np.percentile(mean_like, GENERIC) if n > 1 else np.zeros(n, bool)
    field = np.array([field_of(papers.get(w, {}), w) for w in works])
    family = [papers.get(w, {}).get("family") if papers.get(w, {}).get("role") == "member" else None for w in works]
    S[field[:, None] == field[None, :]] = -1                 # same field: not a twin
    trusted = np.array([w in reliable for w in works])
    known = lambda a, b: family[a] is not None and family[a] == family[b]  # noqa: E731

    def side(i: int) -> dict:
        w = works[i]
        return {"work": w, **papers.get(w, {}),
                "descriptions": [{"problem": rows[k]["problem"], "approach": rows[k]["approach"],
                                  "model": rows[k]["model"][1]} for k in by_work[w]]}

    def entry(a: int, b: int, s: float, trust: str) -> dict:
        return {"similarity": round(s, 4), "trust": trust, "why": why(terms, V[a], V[b]), "a": side(a), "b": side(b)}

    used = defaultdict(int)
    ranked = candidates(S)
    confirmed = similar_pairs(ranked, works, lambda a, b: trusted[a] and trusted[b] and not known(a, b), used, TWINS)
    provisional = similar_pairs(ranked, works, lambda a, b: not (trusted[a] and trusted[b]) and not generic[a]
                                and not generic[b] and not known(a, b), used, TWINS)
    members = [i for i in range(n) if family[i] is not None]
    recovered = sorted(((a, b, float(S[a, b])) for x, a in enumerate(members) for b in members[x + 1:]
                        if known(a, b) and S[a, b] > -1), key=lambda t: -t[2])
    twins = {"method": "tf-idf cosine", "reliable_papers": len(reliable),
             "twins": [entry(a, b, s, "two models agree") for a, b, s in confirmed] +
                      [entry(a, b, s, "one model so far") for a, b, s in provisional],
             "known_cases": [entry(a, b, s, "known case") for a, b, s in recovered]}
    neighbours = {}
    for i, w in enumerate(works):
        best = np.argsort(-S[i])[:NEIGHBOURS]
        neighbours[w] = [[works[j], round(float(S[i, j]), 4)] for j in best if S[i, j] > 0]
    return twins, neighbours


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
               "reliable_percentile": RELIABLE, "distinct_percentile": DISTINCT, "models": []}
    twins, neighbours = {"method": "tf-idf cosine", "twins": [], "known_cases": []}, {}
    if len(rows) >= MIN_DESCRIPTIONS:
        rng = np.random.default_rng(SEED)
        X, terms = vectors(rows)
        base = chance(X, rows, rng)
        pairs = same_paper_pairs(rows)
        threshold = float(np.percentile(base, RELIABLE))
        summary.update(chance_median=round(float(np.median(base)), 4), reliable_above=round(threshold, 4),
                       chance_histogram=histogram(base), models=models(X, rows, pairs, rng))
        twins, neighbours = pairing(X, terms, rows, pairs, papers, threshold)
        summary["reliable_papers"] = twins["reliable_papers"]
    else:
        summary["note"] = f"Fewer than {MIN_DESCRIPTIONS} descriptions so far: nothing to compare yet."
    (out_dir / "models.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "twins.json").write_text(json.dumps(twins, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "neighbours.json").write_text(json.dumps(neighbours, separators=(",", ":")), encoding="utf-8")
    kinds = defaultdict(int)
    for t in twins["twins"]:
        kinds[t["trust"]] += 1
    return {**summary, "twins": dict(kinds), "known_cases": len(twins["known_cases"])}


if __name__ == "__main__":
    print(json.dumps(combine(Path(sys.argv[1])), indent=1)[:2000])
