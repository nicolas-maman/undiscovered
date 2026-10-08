"""The time-sliced backtest: can we predict which distant fields start talking?

Unit: a pair of topics from different OpenAlex domains with at most one
link in all the years up to the cutoff. Label: they connect in the six years
after it. Models are fitted on the 2011 cutoff, whose outcomes end in 2017,
and judged on the 2017 cutoff, so every reported number comes from years the
models never saw when they were fitted.

Models compared (logistic regression on standardised features):
  popularity  the two topics' sizes and growth, how many usable abstracts
              each has, and which pair of domains they come from. Every
              other model includes these.
  network     popularity + the citation network around the pair in the
              train window and in its last three years: degrees, common
              citing topics, Jaccard, Adamic-Adar, co-citation cosine,
              two-step paths, and any earlier link. These are the kinds of
              features that did best in Science4Cast.
  semantic    popularity + how close the two topics' abstracts are
              (centroid cosine, mean of the closest paper pairs), by default
              with TF-IDF fitted on that freeze's abstracts only
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
from .gentle import be_gentle
from .embed import topic_embeddings

RESULTS = Path(__file__).resolve().parent.parent / "results"
TRAIN_CUTOFF, EVAL_CUTOFF = CUTOFFS
DOMAINS = ("Health Sciences", "Life Sciences", "Physical Sciences", "Social Sciences")
DOMAIN_PAIRS = [f"{a} / {b}" for i, a in enumerate(DOMAINS) for b in DOMAINS[i + 1:]]
# One indicator per pair of domains, the first left out as the reference.
DP_FEATURES = ["dp_" + p.lower().replace(" sciences", "").replace(" / ", "_") for p in DOMAIN_PAIRS[1:]]
TOP_PAIRS_ABSTRACTS = 20        # abstracts per topic for the closest-pairs feature
BOOTSTRAP = 2000                # main analysis
BOOTSTRAP_ROBUSTNESS = 1000     # each robustness check
SMALLEST_EFFECT = 0.10          # a gain under 10% of the network model's AP is not worth having

BASE = ["log_size_hi", "log_size_lo", "growth_hi", "growth_lo",
        "log_usable_hi", "log_usable_lo"] + DP_FEATURES
NETWORK = ["log_deg_hi", "log_deg_lo", "log_recent_deg_hi", "log_recent_deg_lo", "log_common",
           "log_recent_common", "jaccard", "adamic_adar", "cocite_cosine", "log_two_hop",
           "prior_links"]
CONTENT = ["centroid_cos", "top_pairs_cos"]
FEATURE_SETS = {
    "popularity": BASE,
    "network": BASE + NETWORK,
    "semantic": BASE + CONTENT,
    "combined": BASE + NETWORK + CONTENT,
}


def load(cutoff: int) -> tuple[list[dict], dict[str, dict]]:
    """Every sampled topic's record at a cutoff. Refuses an incomplete sample."""
    sample = json.loads((DATA / "sample.json").read_text(encoding="utf-8"))
    recs, missing = {}, []
    for t in sample:
        p = DATA / "topics" / str(cutoff) / f"{t['id']}.json"
        rec = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        if not rec or rec.get("format") != collect.FORMAT:
            missing.append(t["id"])
        else:
            recs[t["id"]] = rec
    if missing:
        raise SystemExit(f"{len(missing)} of {len(sample)} topics at {cutoff} are missing or in an "
                         f"old format (first: {missing[0]}); finish the collection first.")
    return sample, recs


def _growth(rec: dict) -> float:
    """Log ratio of works in the last four years of the train window to the first four."""
    start, end = rec["train_window"]
    by_year = rec["works_by_year"]
    early = sum(by_year.get(str(y), 0) for y in range(start, start + 4))
    late = sum(by_year.get(str(y), 0) for y in range(end - 3, end + 1))
    return math.log((late + 1) / (early + 1))


def pair_table(cutoff: int, max_prior_links: int, min_test_links: int, model: str,
               min_size: int = 0) -> dict:
    """Features and labels for every eligible cross-domain pair at one cutoff."""
    topics, recs = load(cutoff)
    if min_size:
        topics = [t for t in topics if recs[t["id"]]["size"] >= min_size]
    ids = [t["id"] for t in topics]
    domain = {t["id"]: t["domain"] for t in topics}

    def link(window: str, a: str, b: str) -> int:
        """Works in a citing b's reference papers plus works in b citing a's."""
        return recs[b][window].get(a, 0) + recs[a][window].get(b, 0)

    # Neighbourhoods: the other topics citing each topic. A topic's citations
    # of itself are left out: they are among its largest counts and say
    # nothing about its neighbours.
    def neighbours(window: str) -> dict[str, dict[str, int]]:
        return {t: {z: c for z, c in recs[t][window].items() if z != t} for t in ids}

    citers, recent = neighbours("cited_by_train"), neighbours("cited_by_recent")
    reach = defaultdict(int)        # how many sampled topics each citing topic cites
    cites = defaultdict(set)        # the sampled topics each topic cites
    for t in ids:
        for z in citers[t]:
            reach[z] += 1
            cites[z].add(t)
    norms = {t: math.sqrt(sum(v * v for v in citers[t].values())) or 1.0 for t in ids}

    usable = embed.usable_abstracts({t: recs[t]["abstracts"] for t in ids})
    emb = topic_embeddings(cutoff, model, usable)
    growth = {t: _growth(recs[t]) for t in ids}

    rows, labels, pairs, links, directions = [], [], [], [], []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if domain[a] == domain[b]:
                continue
            # Not yet connected: linked by at most `max_prior_links` citing
            # works in all the years up to the cutoff, not only the train window.
            prior = link("cited_by_before", a, b) + link("cited_by_train", a, b)
            if prior > max_prior_links:
                continue
            ea, eb = emb.get(a), emb.get(b)
            if ea is None or eb is None:
                continue
            na, nb = set(citers[a]), set(citers[b])
            ra, rb = set(recent[a]), set(recent[b])
            common = na & nb
            aa = sum(1.0 / math.log(reach[z] + 1.0) for z in common if reach[z] > 0)
            dot = sum(citers[a][z] * citers[b][z] for z in common)
            # Two-step paths through a third sampled topic: a cites z and z cites b, or the reverse.
            two_hop = len((cites[a] & nb) - {a, b}) + len((cites[b] & na) - {a, b})
            sims = ea["vecs"][:TOP_PAIRS_ABSTRACTS] @ eb["vecs"][:TOP_PAIRS_ABSTRACTS].T
            sims = sims.toarray() if hasattr(sims, "toarray") else sims    # sparse for TF-IDF
            top = np.sort(np.asarray(sims).ravel())[-5:]
            dp = " / ".join(sorted((domain[a], domain[b])))
            rows.append({
                "log_size_hi": math.log1p(max(recs[a]["size"], recs[b]["size"])),
                "log_size_lo": math.log1p(min(recs[a]["size"], recs[b]["size"])),
                "growth_hi": max(growth[a], growth[b]),
                "growth_lo": min(growth[a], growth[b]),
                "log_usable_hi": math.log(max(len(usable[a]), len(usable[b]))),
                "log_usable_lo": math.log(min(len(usable[a]), len(usable[b]))),
                **{f: float(dp == p) for f, p in zip(DP_FEATURES, DOMAIN_PAIRS[1:])},
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
                "centroid_cos": float(ea["centroid"] @ eb["centroid"]),
                "top_pairs_cos": float(top.mean()),
            })
            ab, ba = recs[b]["cited_by_test"].get(a, 0), recs[a]["cited_by_test"].get(b, 0)
            labels.append(1 if ab + ba >= min_test_links else 0)
            pairs.append((a, b))
            links.append((prior, ab + ba))
            directions.append((ab, ba))
    return {"rows": rows, "labels": np.array(labels), "pairs": pairs, "links": links,
            "directions": directions, "recs": recs,
            "names": {t["id"]: t["name"] for t in topics},
            "fields": {t["id"]: t.get("field", "") for t in topics},
            "subfields": {t["id"]: t.get("subfield", "") for t in topics},
            "domains": domain}


class NotEnoughData(ValueError):
    """A run with no positive or no negative pairs at one of the cutoffs."""


def matrix(rows: list[dict], cols: list[str]) -> np.ndarray:
    return np.array([[r[c] for c in cols] for r in rows], dtype=float).reshape(len(rows), len(cols))


def precision_at(y: np.ndarray, scores: np.ndarray, k: int) -> float:
    k = min(k, len(y))
    order = np.argsort(-scores)[:k]
    return float(y[order].mean()) if k else float("nan")


def _ci(values) -> list[float]:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def fit_score(X_fit: np.ndarray, y_fit: np.ndarray, X_eval: np.ndarray,
              weight: np.ndarray | None = None) -> tuple[np.ndarray, LogisticRegression]:
    """Fit on the 2011 pairs (optionally weighted) and score the 2017 pairs."""
    if weight is not None:
        keep = weight > 0
        X_fit, y_fit, weight = X_fit[keep], y_fit[keep], weight[keep]
    sc = StandardScaler().fit(X_fit, sample_weight=weight)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(sc.transform(X_fit), y_fit, sample_weight=weight)
    return clf.predict_proba(sc.transform(X_eval))[:, 1], clf


def topic_draws(topics_by_domain: dict[str, list[str]], rng: np.random.Generator) -> dict[str, int]:
    """One bootstrap draw: within each domain, its topics drawn with replacement.

    Pairs that share a topic are not independent, so the unit resampled is
    the topic, not the pair; and the sample took the same number of topics
    from each domain, so the draw does too.
    """
    count: dict[str, int] = {}
    for _, ts in sorted(topics_by_domain.items()):
        drawn = np.bincount(rng.integers(0, len(ts), len(ts)), minlength=len(ts))
        count.update(zip(ts, drawn.tolist()))
    return count


def pair_weights(pairs: list[tuple[str, str]], count: dict[str, int]) -> np.ndarray:
    return np.array([count.get(a, 0) * count.get(b, 0) for a, b in pairs], dtype=float)


def bootstrap(fit: dict, ev: dict, X: dict, y_strict: np.ndarray | None, n: int,
              seed: int = 0) -> dict[str, np.ndarray]:
    """Average precision of every model in n replicates, refitting each time.

    Each replicate draws topics, weights the 2011 and 2017 pairs by how often
    their two topics were drawn, refits every model on the weighted 2011
    pairs and scores the weighted 2017 pairs, so the intervals include the
    uncertainty of the fitted weights as well as that of the evaluation.
    """
    by_domain: dict[str, list[str]] = defaultdict(list)
    for t, d in sorted(ev["domains"].items()):
        by_domain[d].append(t)
    rng = np.random.default_rng(seed)
    y_fit, y_ev = fit["labels"], ev["labels"]
    random_scores = np.random.default_rng(1).random(len(y_ev))
    out: dict[str, list[float]] = defaultdict(list)
    while len(out["random"]) < n:
        count = topic_draws(by_domain, rng)
        w_fit, w_ev = pair_weights(fit["pairs"], count), pair_weights(ev["pairs"], count)
        if min((w_fit * y_fit).sum(), (w_fit * (1 - y_fit)).sum(),
               (w_ev * y_ev).sum(), (w_ev * (1 - y_ev)).sum()) == 0:
            continue
        if y_strict is not None and (w_ev * y_strict).sum() == 0:
            continue
        out["random"].append(average_precision_score(y_ev, random_scores, sample_weight=w_ev))
        for name in FEATURE_SETS:
            s, _ = fit_score(X[name][0], y_fit, X[name][1], w_fit)
            out[name].append(average_precision_score(y_ev, s, sample_weight=w_ev))
            if y_strict is not None and name in ("network", "combined"):
                out[name + "_strict"].append(average_precision_score(y_strict, s, sample_weight=w_ev))
    return {k: np.array(v) for k, v in out.items()}


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
        if pos >= min_positive and pos < len(idx):
            for name, s in scores.items():
                entry[name] = float(average_precision_score(y[idx], s[idx]))
        out[key] = entry
    return out


def h1_outcome(diff_ci: list[float], network_ap: float) -> str:
    """supported, negative or inconclusive, as fixed in the plan."""
    if diff_ci[0] > 0:
        return "supported"
    if diff_ci[1] < SMALLEST_EFFECT * network_ap:
        return "negative"
    return "inconclusive"


def run(max_prior_links: int, min_test_links: int, model: str, n_boot: int = BOOTSTRAP,
        strict_links: dict[tuple[str, str], int] | None = None, min_size: int = 0) -> dict:
    """The analysis of research/PREREGISTRATION.md.

    ``strict_links`` maps each 2017 pair to its count of citing works under
    the stricter label (see ``strict.py``); pairs not in it count as zero.
    Without it the report has no strict check and the decision is
    ``incomplete``.
    """
    fit = pair_table(TRAIN_CUTOFF, max_prior_links, min_test_links, model, min_size)
    ev = pair_table(EVAL_CUTOFF, max_prior_links, min_test_links, model, min_size)
    y_fit, y_ev = fit["labels"], ev["labels"]
    for name, y in (("fitting", y_fit), ("evaluation", y_ev)):
        if len(y) == 0:
            raise NotEnoughData(f"no {name} pairs under these settings")
        if y.min() == y.max():
            kind = "positive" if y.max() == 0 else "negative"
            raise NotEnoughData(f"no {kind} {name} pairs under these settings")
    y_strict = None
    if strict_links is not None:
        y_strict = np.array([1 if strict_links.get(p, 0) >= min_test_links else 0 for p in ev["pairs"]])
    report = {
        "config": {"train_cutoff": TRAIN_CUTOFF, "eval_cutoff": EVAL_CUTOFF,
                   "max_prior_links": max_prior_links, "min_test_links": min_test_links,
                   "embedding_model": model, "bootstrap": n_boot, "min_size": min_size,
                   "smallest_effect": SMALLEST_EFFECT},
        "pairs": {"train": len(y_fit), "train_positive": int(y_fit.sum()),
                  "eval": len(y_ev), "eval_positive": int(y_ev.sum()),
                  "eval_base_rate": float(y_ev.mean()) if len(y_ev) else None},
        "models": {},
    }
    X = {name: (matrix(fit["rows"], cols), matrix(ev["rows"], cols)) for name, cols in FEATURE_SETS.items()}
    scores = {"random": np.random.default_rng(1).random(len(y_ev))}
    for name, cols in FEATURE_SETS.items():
        scores[name], clf = fit_score(X[name][0], y_fit, X[name][1])
        report["models"][name] = {"features": cols, "coef": dict(zip(cols, map(float, clf.coef_[0])))}

    boot = bootstrap(fit, ev, X, y_strict, n_boot)
    for name, s in scores.items():
        m = report["models"].setdefault(name, {})
        m["roc_auc"] = float(roc_auc_score(y_ev, s))
        m["average_precision"] = float(average_precision_score(y_ev, s))
        m["average_precision_ci"] = _ci(boot[name])
        for k in (100, 1000):
            m[f"precision_at_{k}"] = precision_at(y_ev, s, k)

    def compare(a: str, b: str, y=y_ev, suffix="") -> dict:
        return {"diff": float(average_precision_score(y, scores[a]) - average_precision_score(y, scores[b])),
                "diff_ci": _ci(boot[a + suffix] - boot[b + suffix])}

    # The hypotheses and the decision rule of research/PREREGISTRATION.md.
    h1, h2, h3 = compare("combined", "network"), compare("network", "popularity"), \
        compare("semantic", "popularity")
    outcome = h1_outcome(h1["diff_ci"], report["models"]["network"]["average_precision"])
    report["hypotheses"] = {
        "H1_combined_beats_network": {**h1, "holds": outcome == "supported", "outcome": outcome},
        "H2_network_beats_popularity": {**h2, "holds": h2["diff"] > 0},
        "H3_semantic_beats_popularity": {**h3, "holds": h3["diff"] > 0},
    }
    hyp = report["hypotheses"]
    if y_strict is None:
        report["strict"] = None
        report["decision"] = "incomplete"
    else:
        st = compare("combined", "network", y=y_strict, suffix="_strict")
        report["strict"] = {**st, "positive": int(y_strict.sum()), "holds": st["diff"] > 0}
        report["decision"] = ("continue" if hyp["H1_combined_beats_network"]["holds"]
                              and hyp["H2_network_beats_popularity"]["holds"]
                              and report["strict"]["holds"] else "stop")
    report["by_domain_pair"] = by_domain_pair(y_ev, scores, ev["pairs"], ev["domains"])

    # Descriptive: which way the new links run, and whether features shifted
    # between the two freezes.
    pos = [d for d, yy in zip(ev["directions"], y_ev) if yy]
    report["directions"] = {"both": sum(1 for a, b in pos if a and b),
                            "one_way": sum(1 for a, b in pos if bool(a) != bool(b))}
    report["feature_shift"] = {
        f: {"fit_mean": float(X["combined"][0][:, j].mean()), "fit_sd": float(X["combined"][0][:, j].std()),
            "eval_mean": float(X["combined"][1][:, j].mean()), "eval_sd": float(X["combined"][1][:, j].std())}
        for j, f in enumerate(FEATURE_SETS["combined"])}

    # The pairs the combined model ranked highest at the 2017 cutoff, with
    # how often they actually cited each other before and after.
    order = np.argsort(-scores["combined"])[:200]

    def side(t: str) -> dict:
        return {"id": t, "name": ev["names"][t], "field": ev["fields"][t], "domain": ev["domains"][t]}

    report["top_predictions"] = [{
        "rank": r + 1,
        "a": side(ev["pairs"][i][0]), "b": side(ev["pairs"][i][1]),
        "score": float(scores["combined"][i]),
        "links_before": int(ev["links"][i][0]), "links_after": int(ev["links"][i][1]),
        "connected_later": int(y_ev[i]),
    } for r, i in enumerate(order)]
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-prior-links", type=int, default=1)
    ap.add_argument("--min-test-links", type=int, default=3)
    ap.add_argument("--model", default=embed.TFIDF,
                    help="tfidf (the plan's main analysis) or a pretrained embedding model")
    ap.add_argument("--data", default="", help="data directory (default research/data)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    be_gentle()
    if args.data:
        global DATA
        DATA = collect.DATA = embed.DATA = Path(args.data).resolve()
    from . import strict
    ev = pair_table(EVAL_CUTOFF, args.max_prior_links, args.min_test_links, args.model)
    strict_links = strict.collect(ev, args.min_test_links)
    report = run(args.max_prior_links, args.min_test_links, args.model, strict_links=strict_links)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS / (
        f"backtest_e{args.max_prior_links}_k{args.min_test_links}_{args.model.replace('/', '_')}.json")
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
              f"{h['diff_ci'][1]:+.4f}] -> {h.get('outcome', 'holds' if h['holds'] else 'does not hold')}")
    print(f"decision (PREREGISTRATION.md): {report['decision']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
