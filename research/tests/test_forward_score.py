"""Tests for scoring the forward test, on a small made-up ranking: no network, no real outcome."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from undiscovered_research import forward_score as fs

DOMAINS = {"T1": "Life Sciences", "T2": "Physical Sciences", "T3": "Social Sciences", "T4": "Health Sciences",
           "T5": "Life Sciences", "T6": "Physical Sciences"}


def made_up(tmp_path: Path) -> Path:
    """A published-looking forward/ folder: every cross-domain pair of six topics, ranked by a made-up score."""
    ids = sorted(DOMAINS)
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:] if DOMAINS[a] != DOMAINS[b]]
    rows = [{"topic_a": a, "name_a": a, "domain_a": DOMAINS[a], "topic_b": b, "name_b": b, "domain_b": DOMAINS[b],
             "prior_links": 0, "network": 1 - k / 100, "popularity": (k * 37 % 13) / 13} for k, (a, b) in enumerate(pairs)]
    with (tmp_path / "ranking-2025.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["rank", *rows[0]], lineterminator="\n")
        w.writeheader()
        for r, row in enumerate(rows, 1):
            w.writerow({"rank": r, **row})
    with (tmp_path / "records-2025.jsonl").open("w", encoding="utf-8") as f:
        for t in ids:
            f.write(json.dumps({"topic": t, "instrument": [f"W{t}"]}) + "\n")
    return tmp_path


class FakeAPI:
    """Citing works by topic: T2's papers are cited 3 times from T1, T4's twice from T3 and once the other way."""

    def __init__(self):
        self.calls = 0

    def paged(self, path, params):
        self.calls += 1
        cited = params["filter"].split("referenced_works:")[1].split(",")[0]
        groups = {"WT2": {"T1": 3}, "WT4": {"T3": 2}, "WT3": {"T4": 1}}.get(cited, {})
        yield {"group_by": [{"key": f"https://openalex.org/{k}", "count": v} for k, v in groups.items()]}


def test_a_window_not_started_is_not_counted(tmp_path):
    api = FakeAPI()
    assert fs.score(2025, made_up(tmp_path), api) == {} and api.calls == 0


def test_pairs_connect_at_three_citing_works_in_either_direction(tmp_path):
    out = fs.score(2026, made_up(tmp_path), FakeAPI())
    main = out["main"]
    assert main["interim"] and main["through"] == 2026 and "check" not in out
    assert main["connected"] == 2                      # T1-T2 (3 one way) and T3-T4 (2 + 1)
    scores = json.loads((tmp_path / "scores" / "main-2026-2031-through-2026.json").read_text())
    assert scores["network"]["average_precision"] == main["network"]["average_precision"]


def test_counts_are_kept_so_a_stopped_run_carries_on(tmp_path):
    folder = made_up(tmp_path)
    fs.score(2026, folder, FakeAPI())
    again = FakeAPI()
    fs.score(2026, folder, again)
    assert again.calls == 0 and len(list((folder / "counts" / "2026-2026").glob("*.json"))) == 6


def test_the_measures_are_scikit_learns_and_the_interval_comes_from_topics():
    rows = [{"rank": str(r + 1), "topic_a": a, "domain_a": DOMAINS[a], "topic_b": b, "domain_b": DOMAINS[b],
             "network": str(1 - r / 10), "popularity": str((r * 7 % 5) / 5)}
            for r, (a, b) in enumerate([("T1", "T2"), ("T1", "T3"), ("T2", "T3"), ("T3", "T4"), ("T4", "T5"),
                                        ("T5", "T6"), ("T1", "T4"), ("T2", "T5")])]
    y = np.array([1, 0, 1, 0, 0, 1, 0, 0])
    m = fs.measures(rows, y, n_boot=200)
    assert m["network"]["average_precision"] == pytest.approx(
        average_precision_score(y, [float(r["network"]) for r in rows]), abs=1e-6)
    lo, hi = m["network_minus_popularity"]["ci"]
    assert lo <= m["network_minus_popularity"]["difference"] <= hi
    assert fs.measures(rows, np.zeros(8, dtype=int))["note"].startswith("no pair")
