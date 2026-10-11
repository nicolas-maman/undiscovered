"""Offline tests for the known-twins units and result: no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("sklearn")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import known_twins  # noqa: E402


def test_benchmark_links_become_openalex_lookups():
    assert known_twins.openalex_ref("https://arxiv.org/abs/2012.06069") == "doi:10.48550/arxiv.2012.06069"
    assert known_twins.openalex_ref("https://arxiv.org/abs/physics/0504137") == "doi:10.48550/arxiv.physics/0504137"
    assert known_twins.openalex_ref("https://pmc.ncbi.nlm.nih.gov/articles/PMC7823953/") == "pmcid:PMC7823953"
    assert known_twins.openalex_ref("https://doi.org/10.1000/xyz") == "doi:10.1000/xyz"
    assert known_twins.openalex_ref("https://example.org/paper.pdf") is None


def test_average_precision():
    assert known_twins.average_precision(["a", "b", "c"], {"a", "c"}) == pytest.approx((1 / 1 + 2 / 3) / 2)


def test_new_units_mix_five_benchmark_papers_with_ordinary_ones():
    index = {"units": [{"unit": "u-100403", "max_avoided": 2, "instructions": "Describe.", "avoid": {}}]}
    gold = [{"work": f"W77{i:02d}"} for i in range(12)]
    ordinary = [f"W{i}" for i in range(100)]
    units = known_twins.add_units(index, gold, {g["work"]: ["gold"] for g in gold}, ordinary,
                                  {w: ["plain"] for w in ordinary})
    assert [u["unit"] for u in units] == ["u-100404", "u-100405", "u-100406"]
    assert [sum(w.startswith("W77") for w in u["works"]) for u in units] == [5, 5, 2]
    assert all(len(u["works"]) == 20 - (5 - n) for u, n in zip(units, [5, 5, 2]))
    assert all(u["quorum"] == 5 and set(u["avoid"]) == set(u["works"]) for u in units)
    flat = [w for u in units for w in u["works"]]
    assert len(flat) == len(set(flat))


def branch(tmp_path: Path, models: int) -> Path:
    """Three families of two fields each and one distractor. The abstracts share nothing across a
    family; every model's descriptions of a family share the family's plain words."""
    plain = {"filter": "estimate a hidden changing state from noisy measurements step by step",
             "rank": "score items by how often they are reached by following links at random",
             "cluster": "split points into groups so that each group is tight around its centre"}
    jargon = {("filter", "a"): "kalman gain covariance innovation control",
              ("filter", "b"): "assimilation ensemble forecast analysis weather",
              ("rank", "a"): "pagerank hyperlink crawl web authority",
              ("rank", "b"): "eigenfactor citation journal prestige bibliometric",
              ("cluster", "a"): "kmeans centroid lloyd quantisation codebook",
              ("cluster", "b"): "ward dendrogram taxon phenetic morphology"}
    gold, k = [], 0
    for fam in plain:
        for field in ("a", "b"):
            gold.append({"work": f"W{k}", "family": fam, "field": field, "role": "member", "method_named": "yes",
                         "text": f"Paper {k}. We study {jargon[(fam, field)]} carefully and report results."})
            k += 1
    gold.append({"work": "W99", "family": "filter", "field": "a", "role": "distractor", "method_named": "yes",
                 "text": "Paper 99. We study kalman gain covariance in a survey of control results."})
    (tmp_path / "known-twins.json").write_text(json.dumps({"papers": gold}), encoding="utf-8")
    fam_of = {g["work"]: g["family"] for g in gold}
    for m in range(models):
        descs = [{"work": g["work"],
                  "problem": (plain[fam_of[g["work"]]] if g["role"] == "member" else "review what others have done"),
                  "approach": f"model {m} words here and there for paper {g['work']}"} for g in gold]
        folder = tmp_path / "results" / f"u-1004{m:02d}"
        folder.mkdir(parents=True)
        (folder / "1.json").write_text(json.dumps(
            {"author": f"v{m}", "model": {"provider": "openai-compatible", "id": f"model-{m}"},
             "descriptions": descs}), encoding="utf-8")
    return tmp_path


def test_the_result_waits_until_every_paper_has_three_models(tmp_path):
    out = known_twins.result(branch(tmp_path, models=2))
    assert out["status"] == "waiting" and out["short_of_models"] == 7


def test_descriptions_that_share_the_problem_find_twins_the_abstracts_miss(tmp_path):
    out = known_twins.result(branch(tmp_path, models=3))
    assert out["status"] == "complete" and out["queries"] == 6 and out["families"] == 3
    assert out["descriptions"]["map"] > out["abstracts"]["map"]
    assert out["descriptions"]["precision_at_1"] == 1.0
    assert out["difference"] == pytest.approx(out["descriptions"]["map"] - out["abstracts"]["map"], abs=1e-3)
