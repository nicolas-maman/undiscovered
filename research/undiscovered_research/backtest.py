"""The time-sliced backtest: can we predict which distant fields start talking?

Unit: a pair of topics from different OpenAlex domains that were (almost) not
connected in the train window. Label: they connect in the test window.
Models are fitted on the 2012 cutoff and judged on the 2017 cutoff, so every
reported number is out of time.

Models compared (logistic regression on standardised features):
  popularity  log sizes of the two topics (preferential attachment)
  network     popularity + structural features of the citation graph in the
              train window: common citing topics, Jaccard, Adamic-Adar,
              co-citation cosine, degrees. This is the Science4Cast-style
              prior art to beat.
  semantic    popularity + similarity of the two topics' random pre-cutoff
              abstracts (centroid cosine, mean of the closest paper pairs)
  combined    all of the above
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from . import collect, embed
from .collect import CUTOFFS, DATA
from .embed import topic_embeddings

RESULTS = Path(__file__).resolve().parent.parent / "results"
TRAIN_CUTOFF, EVAL_CUTOFF = CUTOFFS
FEATURE_SETS = {
    "popularity": ["log_size_a", "log_size_b"],
    "network": ["log_size_a", "log_size_b", "log_deg_a", "log_deg_b",
                "log_common", "jaccard", "adamic_adar", "cocite_cosine"],
    "semantic": ["log_size_a", "log_size_b", "centroid_cos", "top_pairs_cos"],
}
FEATURE_SETS["combined"] = sorted(set(FEATURE_SETS["network"]) | set(FEATURE_SETS["semantic"]))


def load(cutoff: int) -> tuple[list[dict], dict[str, dict]]:
    sample = json.loads((DATA / "sample.json").read_text(encoding="utf-8"))
    recs = {}
    for t in sample:
        p = DATA / "topics" / str(cutoff) / f"{t['id']}.json"
        if p.exists():
            recs[t["id"]] = json.loads(p.read_text(encoding="utf-8"))
    return [t for t in sample if t["id"] in recs], recs


def pair_table(cutoff: int, max_train_links: int, min_test_links: int, model: str) -> dict:
    """Features and labels for every eligible cross-domain pair at one cutoff."""
    topics, recs = load(cutoff)
    ids = [t["id"] for t in topics]
    domain = {t["id"]: t["domain"] for t in topics}

    # A -> B links: works in A citing B's instrument papers, per window.
    def link(window: str, a: str, b: str) -> int:
        return recs[b][window].get(a, 0) + recs[a][window].get(b, 0)

    # Neighbourhoods in the train window: the topics citing each topic.
    citers = {t: recs[t]["cited_by_train"] for t in ids}
    reach = defaultdict(int)        # how many sampled topics each citing topic cites
    for t in ids:
        for z in citers[t]:
            reach[z] += 1
    norms = {t: math.sqrt(sum(v * v for v in citers[t].values())) or 1.0 for t in ids}

    emb = topic_embeddings(cutoff, model, {t: recs[t]["abstracts"] for t in ids})

    rows, labels, pairs = [], [], []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if domain[a] == domain[b]:
                continue
            if link("cited_by_train", a, b) > max_train_links:
                continue
            na, nb = set(citers[a]), set(citers[b])
            common = na & nb
            union = len(na | nb) or 1
            aa = sum(1.0 / math.log(reach[z] + 1.0) for z in common if reach[z] > 0)
            dot = sum(citers[a][z] * citers[b][z] for z in common)
            ea, eb = emb.get(a), emb.get(b)
            if ea is None or eb is None:
                continue
            sims = ea["vecs"] @ eb["vecs"].T
            top = np.sort(sims.ravel())[-5:]
            rows.append({
                "log_size_a": math.log1p(max(recs[a]["size"], recs[b]["size"])),
                "log_size_b": math.log1p(min(recs[a]["size"], recs[b]["size"])),
                "log_deg_a": math.log1p(max(len(na), len(nb))),
                "log_deg_b": math.log1p(min(len(na), len(nb))),
                "log_common": math.log1p(len(common)),
                "jaccard": len(common) / union,
                "adamic_adar": aa,
                "cocite_cosine": dot / (norms[a] * norms[b]),
                "centroid_cos": float(ea["centroid"] @ eb["centroid"]),
                "top_pairs_cos": float(top.mean()),
            })
            labels.append(1 if link("cited_by_test", a, b) >= min_test_links else 0)
            pairs.append((a, b))
    return {"rows": rows, "labels": np.array(labels), "pairs": pairs,
            "names": {t["id"]: t["name"] for t in topics},
            "domains": domain}


def matrix(rows: list[dict], cols: list[str]) -> np.ndarray:
    return np.array([[r[c] for c in cols] for r in rows], dtype=float)


def precision_at(y: np.ndarray, scores: np.ndarray, k: int) -> float:
    k = min(k, len(y))
    order = np.argsort(-scores)[:k]
    return float(y[order].mean()) if k else float("nan")


BOOTSTRAP = 300


def _resamples(y: np.ndarray, n: int = BOOTSTRAP, seed: int = 0) -> list[np.ndarray]:
    """The same bootstrap resamples for every model, so intervals are comparable."""
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        idx = rng.integers(0, len(y), len(y))
        if y[idx].sum() > 0:
            out.append(idx)
    return out


def _ci(values: list[float]) -> list[float]:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def ap_interval(y: np.ndarray, s: np.ndarray, samples: list[np.ndarray]) -> list[float]:
    return _ci([average_precision_score(y[i], s[i]) for i in samples])


def compare(y: np.ndarray, s1: np.ndarray, s2: np.ndarray, samples: list[np.ndarray]) -> dict:
    """AP(s1) - AP(s2), as a point estimate and a 95% bootstrap interval."""
    d = [average_precision_score(y[i], s1[i]) - average_precision_score(y[i], s2[i])
         for i in samples]
    return {"diff": float(average_precision_score(y, s1) - average_precision_score(y, s2)),
            "diff_ci": _ci(d)}


def by_domain_pair(y: np.ndarray, scores: dict[str, np.ndarray], pairs: list[tuple[str, str]],
                   domains: dict[str, str], min_positive: int = 5) -> dict:
    """Average precision per domain pair, where there are enough positives to say anything."""
    groups: dict[str, list[int]] = defaultdict(list)
    for i, (a, b) in enumerate(pairs):
        groups[" / ".join(sorted((domains[a], domains[b])))].append(i)
    out = {}
    for key, idx in sorted(groups.items()):
        idx = np.array(idx)
        pos = int(y[idx].sum())
        entry = {"pairs": int(len(idx)), "positive": pos}
        if pos >= min_positive:
            for name, s in scores.items():
                entry[name] = float(average_precision_score(y[idx], s[idx]))
        out[key] = entry
    return out


def run(max_train_links: int, min_test_links: int, model: str) -> dict:
    train = pair_table(TRAIN_CUTOFF, max_train_links, min_test_links, model)
    test = pair_table(EVAL_CUTOFF, max_train_links, min_test_links, model)
    y_tr, y_te = train["labels"], test["labels"]
    report = {
        "config": {"train_cutoff": TRAIN_CUTOFF, "eval_cutoff": EVAL_CUTOFF,
                   "max_train_links": max_train_links, "min_test_links": min_test_links,
                   "embedding_model": model},
        "pairs": {"train": len(y_tr), "train_positive": int(y_tr.sum()),
                  "eval": len(y_te), "eval_positive": int(y_te.sum()),
                  "eval_base_rate": float(y_te.mean()) if len(y_te) else None},
        "models": {},
    }
    scores = {}
    rng = np.random.default_rng(1)
    scores["random"] = rng.random(len(y_te))
    for name, cols in FEATURE_SETS.items():
        sc = StandardScaler().fit(matrix(train["rows"], cols))
        clf = LogisticRegression(max_iter=2000, class_weight="balanced")
        clf.fit(sc.transform(matrix(train["rows"], cols)), y_tr)
        scores[name] = clf.predict_proba(sc.transform(matrix(test["rows"], cols)))[:, 1]
        report["models"][name] = {"features": cols,
                                  "coef": dict(zip(cols, map(float, clf.coef_[0])))}
    samples = _resamples(y_te)
    for name, s in scores.items():
        m = report["models"].setdefault(name, {})
        m["roc_auc"] = float(roc_auc_score(y_te, s))
        m["average_precision"] = float(average_precision_score(y_te, s))
        m["average_precision_ci"] = ap_interval(y_te, s, samples)
        for k in (100, 1000):
            m[f"precision_at_{k}"] = precision_at(y_te, s, k)

    # The hypotheses and the decision rule of research/PREREGISTRATION.md.
    h1 = compare(y_te, scores["combined"], scores["network"], samples)
    h2 = compare(y_te, scores["network"], scores["popularity"], samples)
    h3 = compare(y_te, scores["semantic"], scores["popularity"], samples)
    report["hypotheses"] = {
        "H1_combined_beats_network": {**h1, "holds": h1["diff_ci"][0] > 0},
        "H2_network_beats_popularity": {**h2, "holds": h2["diff"] > 0},
        "H3_semantic_beats_popularity": {**h3, "holds": h3["diff"] > 0},
    }
    hyp = report["hypotheses"]
    report["decision"] = ("continue" if hyp["H1_combined_beats_network"]["holds"]
                          and hyp["H2_network_beats_popularity"]["holds"] else "stop")
    report["by_domain_pair"] = by_domain_pair(y_te, scores, test["pairs"], test["domains"])

    order = np.argsort(-scores["combined"])[:200]
    report["top_predictions"] = [{
        "a": test["pairs"][i][0], "a_name": test["names"][test["pairs"][i][0]],
        "a_domain": test["domains"][test["pairs"][i][0]],
        "b": test["pairs"][i][1], "b_name": test["names"][test["pairs"][i][1]],
        "b_domain": test["domains"][test["pairs"][i][1]],
        "score": float(scores["combined"][i]), "connected_later": int(y_te[i]),
    } for i in order]
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-train-links", type=int, default=1)
    ap.add_argument("--min-test-links", type=int, default=3)
    ap.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    ap.add_argument("--data", default="", help="data directory (default research/data)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.data:
        global DATA
        DATA = collect.DATA = embed.DATA = Path(args.data).resolve()
    report = run(args.max_train_links, args.min_test_links, args.model)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS / (
        f"backtest_k{args.min_test_links}_{args.model.replace('/', '_')}.json")
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    p = report["pairs"]
    print(f"pairs: train {p['train']} (+{p['train_positive']}), eval {p['eval']} "
          f"(+{p['eval_positive']}, base rate {p['eval_base_rate']:.4f})")
    print(f"{'model':<11} {'AUC':>6} {'AP':>7} {'P@100':>6} {'P@1000':>7}")
    for name in ("random", "popularity", "network", "semantic", "combined"):
        m = report["models"][name]
        print(f"{name:<11} {m['roc_auc']:6.3f} {m['average_precision']:7.4f} "
              f"{m['precision_at_100']:6.2f} {m['precision_at_1000']:7.3f}")
    for key, h in report["hypotheses"].items():
        print(f"{key}: AP diff {h['diff']:+.4f}, 95% CI [{h['diff_ci'][0]:+.4f}, "
              f"{h['diff_ci'][1]:+.4f}] -> {'holds' if h['holds'] else 'does not hold'}")
    print(f"decision (PREREGISTRATION.md): {report['decision']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
