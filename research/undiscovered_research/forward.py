"""The forward test (research/FORWARD-TEST-DRAFT.md): its data and its ranking.

    python -m undiscovered_research.forward collect     # the 300 topics at the end of 2025
    python -m undiscovered_research.forward rank --out forward   # only once the plan is registered

The ranking uses the first test's network and popularity models, refitted
from its 2011 records with its own code and checked against the published
coefficients, and the same features, computed here from map records (which
keep the number of usable abstracts, not their text). ``same_as_backtest``
checks those features against the first test's own, value for value.

Each topic's record is made by the volunteer client's own code
(clients/python, ``mapper.map_topic``), so the forward test ranks exactly
what a map unit would record. Records go to ``research/data_forward``, one
file per topic; a topic already there is not asked for again, so the
command can be run once a day until it reports every topic done. Nothing in
it looks at any outcome: the citations the forward test is scored on have
not been written yet.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from . import backtest, embed
from .gentle import be_gentle

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH.parent / "clients" / "python"))
from undiscovered import mapper  # noqa: E402
from undiscovered.openalex import BudgetExhausted, OpenAlex  # noqa: E402

FREEZE = 2025
SAMPLE = RESEARCH / "data" / "sample.json"          # the first test's 300 topics
OUT = RESEARCH / "data_forward"


def key() -> str:
    path = RESEARCH / ".openalex_key"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def collect(out: Path = OUT, sample: Path = SAMPLE) -> int:
    """Record every topic not yet recorded. Returns how many are still missing."""
    topics = [t["id"] for t in json.loads(sample.read_text(encoding="utf-8"))]
    (out / "records").mkdir(parents=True, exist_ok=True)
    todo = [t for t in topics if not (out / "records" / f"{t}.json").exists()]
    print(f"{len(topics) - len(todo)} of {len(topics)} topics recorded at the end of {FREEZE}")
    with tempfile.TemporaryDirectory(prefix="undiscovered-forward-") as tmp:
        api = OpenAlex(Path(tmp), key())
        for i, t in enumerate(todo, 1):
            try:
                rec = mapper.map_topic(api, t, FREEZE)
            except BudgetExhausted as e:
                print(f"stopped: {e}; run the same command again after it resets")
                break
            path = out / "records" / f"{t}.json"
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
            tmp_path.replace(path)
            left = f" (OpenAlex calls left today: {api.remaining})" if api.remaining is not None else ""
            print(f"{i}/{len(todo)} {t}{left}", flush=True)
    missing = sum(not (out / "records" / f"{t}.json").exists() for t in topics)
    print("every topic recorded" if not missing else f"{missing} topics still to record")
    return missing


MODELS = ("network", "popularity")
TOLERANCE = 1e-4            # largest difference from a published coefficient that is accepted


def features(recs: dict[str, dict], topics: list[dict], usable: dict[str, int]) -> tuple[list[dict], list[tuple]]:
    """The first test's base and network features for every eligible pair, in its order.

    ``usable`` is each topic's number of usable abstracts. Eligible, as in the
    first test: topics from different domains, at most one citing work between
    them in all the years up to the freeze, and both with at least
    embed.MIN_ABSTRACTS usable abstracts. Returns the rows and, for each, the
    pair and its prior links.
    """
    ids = [t["id"] for t in topics]
    domain = {t["id"]: t["domain"] for t in topics}

    def link(window: str, a: str, b: str) -> int:
        return recs[b][window].get(a, 0) + recs[a][window].get(b, 0)

    def neighbours(window: str) -> dict[str, dict[str, int]]:
        return {t: {z: c for z, c in recs[t][window].items() if z != t} for t in ids}

    citers, recent = neighbours("cited_by_train"), neighbours("cited_by_recent")
    reach, cites = defaultdict(int), defaultdict(set)
    for t in ids:
        for z in citers[t]:
            reach[z] += 1
            cites[z].add(t)
    norms = {t: math.sqrt(sum(v * v for v in citers[t].values())) or 1.0 for t in ids}
    growth = {t: backtest._growth(recs[t]) for t in ids}
    rows, pairs = [], []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if domain[a] == domain[b]:
                continue
            prior = link("cited_by_before", a, b) + link("cited_by_train", a, b)
            if prior > 1 or min(usable[a], usable[b]) < embed.MIN_ABSTRACTS:
                continue
            na, nb = set(citers[a]), set(citers[b])
            ra, rb = set(recent[a]), set(recent[b])
            common = na & nb
            aa = sum(1.0 / math.log(reach[z] + 1.0) for z in common if reach[z] > 0)
            dot = sum(citers[a][z] * citers[b][z] for z in common)
            two_hop = len((cites[a] & nb) - {a, b}) + len((cites[b] & na) - {a, b})
            dp = " / ".join(sorted((domain[a], domain[b])))
            rows.append({
                "log_size_hi": math.log1p(max(recs[a]["size"], recs[b]["size"])),
                "log_size_lo": math.log1p(min(recs[a]["size"], recs[b]["size"])),
                "growth_hi": max(growth[a], growth[b]),
                "growth_lo": min(growth[a], growth[b]),
                "log_usable_hi": math.log(max(usable[a], usable[b])),
                "log_usable_lo": math.log(min(usable[a], usable[b])),
                **{f: float(dp == p) for f, p in zip(backtest.DP_FEATURES, backtest.DOMAIN_PAIRS[1:])},
                "log_deg_hi": math.log1p(max(len(na), len(nb))),
                "log_deg_lo": math.log1p(min(len(na), len(nb))),
                "log_recent_deg_hi": math.log1p(max(len(ra), len(rb))),
                "log_recent_deg_lo": math.log1p(min(len(ra), len(rb))),
                "log_common": math.log1p(len(common)),
                "log_recent_common": math.log1p(len(ra & rb)),
                "jaccard": len(common) / (len(na | nb) or 1),
                "adamic_adar": aa,
                "cocite_cosine": dot / (norms[a] * norms[b]),
                "log_two_hop": math.log1p(two_hop),
                "prior_links": float(prior),
            })
            pairs.append((a, b, prior))
    return rows, pairs


def same_as_backtest(cutoff: int = 2017) -> float:
    """Largest difference between these features and the first test's own, on its records at ``cutoff``."""
    table = backtest.pair_table(cutoff, 1, 3, embed.TFIDF)
    topics, recs = backtest.load(cutoff)
    usable = {t: len(v) for t, v in embed.usable_abstracts({t: recs[t]["abstracts"] for t in recs}).items()}
    usable = {t["id"]: usable.get(t["id"], 0) for t in topics}
    rows, pairs = features(recs, topics, usable)
    if [(a, b) for a, b, _ in pairs] != [tuple(p) for p in table["pairs"]]:
        raise AssertionError("the eligible pairs differ from the first test's")
    cols = backtest.FEATURE_SETS["network"]
    return float(np.abs(backtest.matrix(rows, cols) - backtest.matrix(table["rows"], cols)).max())


def fit_models() -> dict[str, dict]:
    """Both models refitted on the first test's 2011 pairs, checked against the published coefficients."""
    published = json.loads((RESEARCH.parent / "data" / "backtest.json").read_text(encoding="utf-8"))["report"]
    cfg = published["config"]
    fit = backtest.pair_table(cfg["train_cutoff"], cfg["max_prior_links"], cfg["min_test_links"], cfg["embedding_model"])
    out = {}
    for name in MODELS:
        cols = backtest.FEATURE_SETS[name]
        X = backtest.matrix(fit["rows"], cols)
        sc = StandardScaler().fit(X)
        clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(sc.transform(X), fit["labels"])
        worst = max(abs(c - published["models"][name]["coef"][f]) for f, c in zip(cols, clf.coef_[0]))
        if worst > TOLERANCE:
            raise SystemExit(f"the refitted {name} model differs from the published one by {worst:.2g}; nothing ranked")
        out[name] = {"features": cols, "coef": [float(c) for c in clf.coef_[0]], "intercept": float(clf.intercept_[0]),
                     "mean": [float(m) for m in sc.mean_], "scale": [float(s) for s in sc.scale_],
                     "largest_difference_from_published": worst}
    return out


def score(model: dict, rows: list[dict]) -> np.ndarray:
    """The model's probability for each row, from model.json alone."""
    X = backtest.matrix(rows, model["features"])
    z = (X - np.array(model["mean"])) / np.array(model["scale"])
    return 1.0 / (1.0 + np.exp(-(z @ np.array(model["coef"]) + model["intercept"])))


def rank(out: Path, data: Path = OUT, sample: Path = SAMPLE) -> None:
    """Write the ranking, both models and the records, with their checksums, to ``out``."""
    topics = json.loads(sample.read_text(encoding="utf-8"))
    recs = {t["id"]: json.loads((data / "records" / f"{t['id']}.json").read_text(encoding="utf-8")) for t in topics}
    models = fit_models()
    rows, pairs = features(recs, topics, {t: r["usable_abstracts"] for t, r in recs.items()})
    scores = {name: score(models[name], rows) for name in MODELS}
    info = {t["id"]: t for t in topics}
    order = sorted(range(len(pairs)), key=lambda k: (-scores["network"][k], pairs[k][0], pairs[k][1]))
    out.mkdir(parents=True, exist_ok=True)
    with (out / "ranking-2025.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "topic_a", "name_a", "domain_a", "topic_b", "name_b", "domain_b", "prior_links",
                    "network", "popularity"])
        for r, k in enumerate(order, 1):
            a, b, prior = pairs[k]
            w.writerow([r, a, info[a]["name"], info[a]["domain"], b, info[b]["name"], info[b]["domain"], prior,
                        f"{scores['network'][k]:.6f}", f"{scores['popularity'][k]:.6f}"])
    (out / "model.json").write_text(json.dumps(
        {"score": "1 / (1 + exp(-(intercept + sum(coef[i] * (x[i] - mean[i]) / scale[i]))))", **models},
        indent=1), encoding="utf-8", newline="\n")
    with (out / "records-2025.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for t in sorted(recs):
            f.write(json.dumps(recs[t], sort_keys=True) + "\n")
    names = ["model.json", "ranking-2025.csv", "records-2025.jsonl"]
    sums = "".join(f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}\n" for n in names)
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    print(f"{len(pairs)} pairs ranked -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["collect", "check", "rank"])
    ap.add_argument("--out", default="", help="for rank: the folder to write the ranking to")
    args = ap.parse_args()
    be_gentle()
    if args.step == "collect":
        collect()
    elif args.step == "check":
        print(f"largest difference from the first test's features at 2017: {same_as_backtest():.3g}")
    else:
        if not args.out:
            raise SystemExit("rank needs --out")
        rank(Path(args.out))


if __name__ == "__main__":
    main()
