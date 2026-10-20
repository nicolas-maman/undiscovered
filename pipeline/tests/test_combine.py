"""Offline tests for combining descriptions: model agreement, twins and the open index."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

pytest.importorskip("sklearn")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import combine  # noqa: E402

VOCAB = ["river", "sediment", "pressure", "valve", "enzyme", "membrane", "voter", "ballot", "crystal", "lattice",
         "signal", "noise", "orbit", "comet", "forest", "canopy", "market", "price", "protein", "fold", "wave",
         "tide", "gene", "promoter", "battery", "anode", "school", "teacher", "virus", "host", "glacier", "melt",
         "bridge", "load", "laser", "pulse", "neuron", "spike", "soil", "root"]


def write_branch(tmp_path: Path, n_papers: int = 40) -> Path:
    """Papers in two domains; alice and bob describe each with its own words, carol vaguely.

    W0 (Life) and W1 (Physical) are planted twins: the same problem, worded the same way.
    """
    rng = random.Random(1)
    papers, words = {}, {}
    for i in range(n_papers):
        w = f"W{i}"
        papers[w] = {"topic": f"T{i}", "topic_name": f"Topic {i}", "domain": "Life Sciences" if i % 2 == 0 else "Physical Sciences"}
        words[w] = rng.sample(VOCAB, 4)
    words["W1"] = words["W0"]
    (tmp_path / "papers.json").write_text(json.dumps(papers), encoding="utf-8")

    generic = ["process", "system", "change", "pattern", "effect", "factor", "outcome", "method", "trend", "result"]

    def desc(w, vague=False):
        if vague:       # generic words that vary, as a weak model's would, but say nothing about the paper
            a, b, c = rng.sample(generic, 3)
            return {"work": w, "problem": f"Study how the {a} and the {b} change over time in a careful way.",
                    "approach": f"Collect measurements of the {c} and compare them with what a simple model expects."}
        a, b, c, d = words[w]
        return {"work": w, "problem": f"Estimate how the {a} responds to the {b} when conditions shift.",
                "approach": f"Measure the {c} and the {d} repeatedly and fit the {a} to them."}

    def result(issue, author, model, descs):
        folder = tmp_path / "results" / f"u-1{issue:05d}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{issue}.json").write_text(json.dumps(
            {"author": author, "model": {"provider": "openai-compatible", "id": model}, "descriptions": descs}),
            encoding="utf-8")

    ids = list(papers)
    result(1, "alice", "model-a", [desc(w) for w in ids])
    result(2, "bob", "model-b", [desc(w) for w in ids[: n_papers // 2]])
    result(3, "carol", "model-vague", [desc(w, vague=True) for w in ids[n_papers // 2:]])
    return tmp_path


def test_models_that_describe_each_paper_agree_more_than_a_vague_one(tmp_path):
    summary = combine.combine(write_branch(tmp_path))
    by = {m["id"]: m for m in json.loads((tmp_path / "combined" / "models.json").read_text())["models"]}
    assert by["model-b"]["agreement"] > by["model-b"]["chance"]
    assert by["model-vague"]["agreement"] < by["model-b"]["agreement"]
    assert by["model-a"]["descriptions"] == 40 and by["model-a"]["papers"] == 40
    assert summary["descriptions"] == 80


def twins_of(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "combined" / "twins.json").read_text())


def test_the_planted_twins_come_first_and_vague_papers_are_never_confirmed(tmp_path):
    combine.combine(write_branch(tmp_path))
    twins = twins_of(tmp_path)["twins"]
    confirmed = [t for t in twins if t["trust"] == "two models agree"]
    assert {confirmed[0]["a"]["work"], confirmed[0]["b"]["work"]} == {"W0", "W1"}
    vague = {f"W{i}" for i in range(20, 40)}
    assert not any(t["a"]["work"] in vague or t["b"]["work"] in vague for t in confirmed)
    assert all(t["a"]["domain"] != t["b"]["domain"] for t in twins)
    assert [w for w, _ in confirmed[0]["why"]][:4] and all(weight > 0 for _, weight in confirmed[0]["why"])
    assert {t["trust"] for t in twins} == {"two models agree", "one model so far"}


def test_boilerplate_two_models_share_for_every_paper_is_never_confirmed(tmp_path):
    """Two models that write one generic text for every paper agree perfectly on each paper, beating
    chance; only the paper's likeness to every other paper gives them away."""
    branch = write_branch(tmp_path)
    papers = json.loads((branch / "papers.json").read_text())
    generic = [f"W{i}" for i in range(40, 50)]                  # papers nobody else has described
    papers.update({w: {"topic": f"T{w}", "domain": ["Life Sciences", "Physical Sciences"][i % 2]}
                   for i, w in enumerate(generic)})
    (branch / "papers.json").write_text(json.dumps(papers))
    for issue, model in ((7, "model-same-1"), (8, "model-same-2")):
        folder = branch / "results" / f"u-1{issue:05d}"
        folder.mkdir(parents=True)
        descs = [{"work": w, "problem": "Study how the measured outcome changes when conditions differ.",
                  "approach": "Collect the data, compare the groups and fit a simple model to the measurements."}
                 for w in generic]
        (folder / f"{issue}.json").write_text(json.dumps(
            {"author": "erin", "model": {"provider": "openai-compatible", "id": model}, "descriptions": descs}))
    combine.combine(branch)
    confirmed = {w for t in twins_of(tmp_path)["twins"] if t["trust"] == "two models agree"
                 for w in (t["a"]["work"], t["b"]["work"])}
    assert confirmed and not confirmed & set(generic)


def test_pairs_cross_fields_not_domains_and_known_cases_are_listed_apart(tmp_path):
    branch = write_branch(tmp_path)
    papers = json.loads((branch / "papers.json").read_text())
    papers["W0"].update(domain="Physical Sciences", field="Earth and Planetary Sciences")
    papers["W1"].update(domain="Physical Sciences", field="Mathematics")
    (branch / "papers.json").write_text(json.dumps(papers))
    combine.combine(branch)
    first = next(t for t in twins_of(tmp_path)["twins"] if t["trust"] == "two models agree")
    assert {first["a"]["work"], first["b"]["work"]} == {"W0", "W1"}          # one domain, two fields: a pair

    papers["W1"]["field"] = "Earth and Planetary Sciences"                       # one field: never a pair
    (branch / "papers.json").write_text(json.dumps(papers))
    combine.combine(branch)
    assert not any({t["a"]["work"], t["b"]["work"]} == {"W0", "W1"} for t in twins_of(tmp_path)["twins"])

    papers["W1"]["field"] = "Mathematics"
    (branch / "papers.json").write_text(json.dumps(papers))
    (branch / "known-twins.json").write_text(json.dumps({"papers": [
        {"work": "W0", "family": "hawkes", "role": "member"}, {"work": "W1", "family": "hawkes", "role": "member"}]}))
    combine.combine(branch)
    out = twins_of(tmp_path)
    assert not any({t["a"]["work"], t["b"]["work"]} == {"W0", "W1"} for t in out["twins"])
    assert {out["known_cases"][0]["a"]["work"], out["known_cases"][0]["b"]["work"]} == {"W0", "W1"}


def test_every_described_paper_has_its_nearest_papers_from_other_fields(tmp_path):
    combine.combine(write_branch(tmp_path))
    near = json.loads((tmp_path / "combined" / "neighbours.json").read_text())
    papers = json.loads((tmp_path / "papers.json").read_text())
    assert len(near) == 40 and near["W0"][0][0] == "W1"
    assert all(papers[w]["domain"] != papers[n]["domain"] for w, ns in near.items() for n, _ in ns)


def test_the_open_index_has_one_line_per_paper(tmp_path):
    combine.combine(write_branch(tmp_path))
    lines = (tmp_path / "combined" / "descriptions.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert len(lines) == 40 and first["descriptions"][0]["model"]["id"] == "model-a"


def test_too_few_descriptions_say_so_instead_of_guessing(tmp_path):
    summary = combine.combine(write_branch(tmp_path, n_papers=10))
    assert "nothing to compare yet" in summary["note"] and summary["twins"] == {}


def test_two_volunteers_with_the_same_model_do_not_count_as_agreeing(tmp_path):
    branch = write_branch(tmp_path)
    folder = branch / "results" / "u-100009"
    folder.mkdir(parents=True)
    same = json.loads((branch / "results" / "u-100001" / "1.json").read_text())
    (folder / "9.json").write_text(json.dumps({**same, "author": "dave"}), encoding="utf-8")   # dave runs model-a too
    _papers, rows = combine.load(branch)
    pairs = combine.same_paper_pairs(rows)
    assert pairs and all(rows[a]["model"] != rows[b]["model"] for a, b in pairs)
    assert not any({rows[a]["author"], rows[b]["author"]} == {"alice", "dave"} for a, b in pairs)


def test_each_pair_says_whether_its_papers_already_cite_each_other(tmp_path):
    import cites
    combine.combine(write_branch(tmp_path))
    first = twins_of(tmp_path)["twins"][0]
    a, b = first["a"]["work"], first["b"]["work"]
    out = cites.mark(tmp_path, fetch=lambda works, session: {a: {b, "W999"}})
    marked = twins_of(tmp_path)["twins"]
    assert marked[0]["cites"] == "a cites b" and out["pairs"] == len(marked)
    assert all(t["cites"] == "neither" for t in marked[1:] if a not in (t["a"]["work"], t["b"]["work"]))
    assert cites.verdict("W1", "W2", {"W1": {"W2"}, "W2": {"W1"}}) == "both"
