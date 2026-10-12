"""Scoring the forward test (research/FORWARD-TEST.md), once a year from 2027.

    python -m undiscovered_research.forward_score --through 2026

Reads the ranking as published (forward/ranking-2025.csv) and each topic's
reference papers from the published records (forward/records-2025.jsonl),
never a recomputed version of either. For each window it counts the works
published from its first year to `--through` that cite a topic's reference
papers, by primary topic, with the map record's own query, and writes
forward/scores/<window>-through-<year>.json with the plan's measures. A
window not yet complete is labelled interim; the result is the count once
2031 (the main window) or 2032 (the check) is complete.

Counts are kept per topic in forward/counts/<first>-<through>/, published
with the scores, so a run stopped by the day's OpenAlex allowance carries on
where it stopped. An OpenAlex key, if any, is read from OPENALEX_API_KEY.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from . import backtest
from .gentle import be_gentle

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients" / "python"))
from undiscovered.mapper import citing_counts  # noqa: E402
from undiscovered.openalex import BudgetExhausted, OpenAlex  # noqa: E402

FORWARD = ROOT / "forward"
WINDOWS = {"main": (2026, 2031), "check": (2027, 2032)}
LINKS = 3                   # citing works, in either direction, that make a pair connected
BOOTSTRAP = 2000
SEED = 2025


def published_ranking(forward: Path = FORWARD) -> list[dict]:
    with (forward / "ranking-2025.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def published_records(forward: Path = FORWARD) -> dict[str, dict]:
    with (forward / "records-2025.jsonl").open(encoding="utf-8") as f:
        return {r["topic"]: r for r in map(json.loads, f)}


def count(api, recs: dict[str, dict], first: int, through: int, folder: Path) -> dict[str, dict[str, int]] | None:
    """Each topic's citing works by topic in [first, through]; None if the allowance ran out first."""
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for t in sorted(recs):
        path = folder / f"{t}.json"
        if not path.exists():
            try:
                counts = citing_counts(api, recs[t]["instrument"], first, through)
            except BudgetExhausted as e:
                print(f"stopped: {e}; run again after it resets")
                return None
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(counts, sort_keys=True), encoding="utf-8")
            tmp.replace(path)
        out[t] = json.loads(path.read_text(encoding="utf-8"))
    return out


def labels(rows: list[dict], counts: dict[str, dict[str, int]]) -> np.ndarray:
    """1 for a pair connected by at least LINKS citing works, in either direction."""
    return np.array([int(counts[r["topic_b"]].get(r["topic_a"], 0) + counts[r["topic_a"]].get(r["topic_b"], 0) >= LINKS)
                     for r in rows])


def measures(rows: list[dict], y: np.ndarray, n_boot: int = BOOTSTRAP) -> dict:
    """The plan's measures for the published ranking against these labels."""
    out = {"pairs": len(rows), "connected": int(y.sum()), "chance": round(float(y.mean()), 6)}
    if y.sum() == 0 or y.sum() == len(y):
        return {**out, "note": "no pair, or every pair, is connected so far: nothing to rank against"}
    net = np.array([float(r["network"]) for r in rows])
    pop = np.array([float(r["popularity"]) for r in rows])
    order = np.argsort([int(r["rank"]) for r in rows])
    out.update({
        "network": {"average_precision": round(float(average_precision_score(y, net)), 6),
                    "roc_auc": round(float(roc_auc_score(y, net)), 6),
                    "precision_at_100": round(float(y[order[:100]].mean()), 4)},
        "popularity": {"average_precision": round(float(average_precision_score(y, pop)), 6),
                       "roc_auc": round(float(roc_auc_score(y, pop)), 6)}})
    by_domain = defaultdict(set)
    for r in rows:
        by_domain[r["domain_a"]].add(r["topic_a"])
        by_domain[r["domain_b"]].add(r["topic_b"])
    topics = {d: sorted(ts) for d, ts in by_domain.items()}
    pairs = [(r["topic_a"], r["topic_b"]) for r in rows]
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(n_boot):
        w = backtest.pair_weights(pairs, backtest.topic_draws(topics, rng))
        if (w * y).sum() == 0:
            diffs.append(np.nan)
            continue
        diffs.append(average_precision_score(y, net, sample_weight=w) - average_precision_score(y, pop, sample_weight=w))
    lo, hi = np.nanpercentile(diffs, [2.5, 97.5])
    diff = out["network"]["average_precision"] - out["popularity"]["average_precision"]
    out["network_minus_popularity"] = {"difference": round(diff, 6), "ci": [round(float(lo), 6), round(float(hi), 6)],
                                       "holds": bool(lo > 0)}
    return out


def score(through: int, forward: Path = FORWARD, api=None) -> dict[str, dict]:
    rows, recs = published_ranking(forward), published_records(forward)
    written = {}
    for name, (first, last) in WINDOWS.items():
        if through < first:
            print(f"{name}: its window starts in {first}; nothing to count yet")
            continue
        end = min(through, last)
        api = api or OpenAlex(Path(tempfile.mkdtemp(prefix="undiscovered-score-")), os.environ.get("OPENALEX_API_KEY", ""))
        counts = count(api, recs, first, end, forward / "counts" / f"{first}-{end}")
        if counts is None:
            break
        result = {"window": [first, last], "through": end, "interim": end < last,
                  "plan": "research/FORWARD-TEST.md", **measures(rows, labels(rows, counts))}
        (forward / "scores").mkdir(exist_ok=True)
        path = forward / "scores" / f"{name}-{first}-{last}-through-{end}.json"
        path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
        written[name] = result
        print(f"{name}: {result.get('connected')} of {result['pairs']} pairs connected through {end} -> {path.name}")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--through", type=int, required=True, help="the last complete year to count")
    args = ap.parse_args()
    be_gentle()
    score(args.through)


if __name__ == "__main__":
    main()
