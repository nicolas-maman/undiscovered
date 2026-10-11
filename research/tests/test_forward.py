"""Tests for the forward test's ranking code: no network, and no 2025 ranking is made."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from undiscovered_research import backtest, forward


def record(size: int, train: dict, before: dict | None = None, recent: dict | None = None) -> dict:
    return {"size": size, "train_window": [2018, 2025], "works_by_year": {str(y): size // 8 for y in range(2018, 2026)},
            "cited_by_train": train, "cited_by_recent": recent or {}, "cited_by_before": before or {}}


def test_only_distant_unconnected_pairs_with_enough_abstracts_are_ranked():
    topics = [{"id": "T1", "domain": "Life Sciences"}, {"id": "T2", "domain": "Physical Sciences"},
              {"id": "T3", "domain": "Physical Sciences"}, {"id": "T4", "domain": "Social Sciences"},
              {"id": "T5", "domain": "Health Sciences"}]
    recs = {"T1": record(800, {"T9": 5}), "T2": record(400, {"T9": 2, "T1": 1}),
            "T3": record(300, {"T1": 2}),                      # T1-T3: two links already
            "T4": record(200, {"T9": 1}), "T5": record(100, {})}
    usable = {"T1": 30, "T2": 20, "T3": 25, "T4": 12, "T5": 4}  # T5: too few usable abstracts
    rows, pairs = forward.features(recs, topics, usable)
    assert [(a, b) for a, b, _ in pairs] == [("T1", "T2"), ("T1", "T4"), ("T2", "T4"), ("T3", "T4")]
    first = rows[0]
    assert first["prior_links"] == 1.0 and first["log_common"] == pytest.approx(np.log1p(1))   # both cited by T9
    assert set(first) == set(backtest.FEATURE_SETS["network"])


def test_scores_from_model_json_alone_equal_scikit_learns():
    rng = np.random.default_rng(0)
    cols = backtest.FEATURE_SETS["popularity"]
    X = rng.normal(size=(200, len(cols))) * 3 + 1
    y = (X[:, 0] + rng.normal(size=200) > 1).astype(int)
    sc = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(sc.transform(X), y)
    model = {"features": cols, "coef": list(clf.coef_[0]), "intercept": float(clf.intercept_[0]),
             "mean": list(sc.mean_), "scale": list(sc.scale_)}
    rows = [dict(zip(cols, x)) for x in X[:20]]
    assert np.allclose(forward.score(model, rows), clf.predict_proba(sc.transform(X[:20]))[:, 1])


def test_the_features_are_the_first_tests_own():
    if not (backtest.DATA / "sample.json").exists():
        pytest.skip("needs the first test's records (research/data)")
    assert forward.same_as_backtest(2017) == 0.0
