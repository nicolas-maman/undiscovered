"""Offline tests: no network, no model download."""

from __future__ import annotations

import json

import numpy as np
import pytest

from undiscovered_research import backtest, collect, openalex


def test_abstract_text_rebuilds_word_order():
    inverted = {"fish": [0], "oil": [1], "thins": [2], "blood": [4], "the": [3]}
    assert openalex.abstract_text(inverted) == "fish oil thins the blood"
    assert openalex.abstract_text(None) == ""


def test_short_id():
    assert openalex.short_id("https://openalex.org/T10005") == "T10005"


def test_sample_topics_is_balanced_and_reproducible():
    topics = [{"id": f"T{i}", "domain": d} for i, d in
              enumerate(["Physical Sciences", "Life Sciences", "Health Sciences", "Social Sciences"] * 30)]
    a = collect.sample_topics(topics, 5, seed=7)
    b = collect.sample_topics(topics, 5, seed=7)
    assert [t["id"] for t in a] == [t["id"] for t in b]
    counts = {}
    for t in a:
        counts[t["domain"]] = counts.get(t["domain"], 0) + 1
    assert set(counts.values()) == {5}


def test_precision_at():
    y = np.array([1, 0, 1, 0])
    s = np.array([0.9, 0.8, 0.7, 0.1])
    assert backtest.precision_at(y, s, 1) == 1.0
    assert backtest.precision_at(y, s, 2) == 0.5


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Four topics in two domains; A-C stay apart, A-D connect after the cutoff."""
    topics = [
        {"id": "TA", "name": "a", "domain": "Life Sciences"},
        {"id": "TB", "name": "b", "domain": "Life Sciences"},
        {"id": "TC", "name": "c", "domain": "Physical Sciences"},
        {"id": "TD", "name": "d", "domain": "Physical Sciences"},
    ]
    (tmp_path / "sample.json").write_text(json.dumps(topics))
    citing = {  # topic -> (cited_by_train, cited_by_test)
        "TA": ({"TB": 9, "TX": 4}, {"TB": 9, "TD": 5}),
        "TB": ({"TA": 7, "TX": 2}, {"TA": 6}),
        "TC": ({"TD": 3}, {"TD": 3}),
        "TD": ({"TC": 2, "TX": 1}, {"TC": 2}),
    }
    for cutoff in collect.CUTOFFS:
        d = tmp_path / "topics" / str(cutoff)
        d.mkdir(parents=True)
        for tid, (tr, te) in citing.items():
            d.joinpath(f"{tid}.json").write_text(json.dumps({
                "topic": tid, "size": 100, "instrument": ["W1"],
                "abstracts": [{"id": "W1", "text": "x"}],
                "cited_by_train": tr, "cited_by_test": te,
            }))
    monkeypatch.setattr(backtest, "DATA", tmp_path)
    vec = {"TA": [1.0, 0.0], "TB": [0.9, 0.1], "TC": [0.0, 1.0], "TD": [0.7, 0.7]}

    def fake_embeddings(cutoff, model, abstracts):
        out = {}
        for t in abstracts:
            v = np.array([vec[t]], dtype=np.float32)
            v /= np.linalg.norm(v)
            out[t] = {"vecs": v, "centroid": v[0]}
        return out

    monkeypatch.setattr(backtest, "topic_embeddings", fake_embeddings)
    return tmp_path


def test_pair_table_keeps_only_unconnected_cross_domain_pairs(world):
    table = backtest.pair_table(2017, max_train_links=1, min_test_links=3, model="fake")
    pairs = set(table["pairs"])
    assert ("TA", "TB") not in pairs                     # same domain
    assert pairs == {("TA", "TC"), ("TA", "TD"), ("TB", "TC"), ("TB", "TD")}
    label = dict(zip(table["pairs"], table["labels"]))
    assert label[("TA", "TD")] == 1                      # 5 citing works after the cutoff
    assert label[("TA", "TC")] == 0


def test_pair_table_features_reflect_shared_citers(world):
    table = backtest.pair_table(2017, max_train_links=1, min_test_links=3, model="fake")
    rows = dict(zip(table["pairs"], table["rows"]))
    # TA and TD are both cited by TX; TA and TC share no citing topic.
    assert rows[("TA", "TD")]["log_common"] > rows[("TA", "TC")]["log_common"]
    assert rows[("TA", "TD")]["centroid_cos"] > rows[("TA", "TC")]["centroid_cos"]


def test_full_run_produces_the_preregistered_report(world):
    report = backtest.run(max_train_links=1, min_test_links=3, model="fake")
    assert set(report["models"]) == {"random", "popularity", "network", "semantic", "combined"}
    for m in report["models"].values():
        lo, hi = m["average_precision_ci"]
        assert 0.0 <= lo <= hi <= 1.0
    hyp = report["hypotheses"]
    assert set(hyp) == {"H1_combined_beats_network", "H2_network_beats_popularity",
                        "H3_semantic_beats_popularity"}
    h1 = hyp["H1_combined_beats_network"]
    assert h1["holds"] == (h1["diff_ci"][0] > 0)
    expected = "continue" if h1["holds"] and hyp["H2_network_beats_popularity"]["holds"] else "stop"
    assert report["decision"] == expected
    assert report["pairs"]["eval_positive"] == 1
    assert "Life Sciences / Physical Sciences" in report["by_domain_pair"]


def test_compare_is_zero_against_itself():
    y = np.array([1, 0, 1, 0, 0, 1])
    s = np.array([0.9, 0.2, 0.8, 0.3, 0.1, 0.7])
    samples = backtest._resamples(y, n=50)
    c = backtest.compare(y, s, s, samples)
    assert c["diff"] == 0.0 and c["diff_ci"] == [0.0, 0.0]
