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


def test_the_planted_twins_come_first_and_vague_papers_never_pair(tmp_path):
    combine.combine(write_branch(tmp_path))
    twins = json.loads((tmp_path / "combined" / "twins.json").read_text())["twins"]
    assert {twins[0]["a"]["work"], twins[0]["b"]["work"]} == {"W0", "W1"}
    vague = {f"W{i}" for i in range(20, 40)}
    assert not any(t["a"]["work"] in vague or t["b"]["work"] in vague for t in twins)
    assert all(t["a"]["domain"] != t["b"]["domain"] for t in twins)


def test_the_open_index_has_one_line_per_paper(tmp_path):
    combine.combine(write_branch(tmp_path))
    lines = (tmp_path / "combined" / "descriptions.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert len(lines) == 40 and first["descriptions"][0]["model"]["id"] == "model-a"


def test_too_few_descriptions_say_so_instead_of_guessing(tmp_path):
    summary = combine.combine(write_branch(tmp_path, n_papers=10))
    assert "nothing to compare yet" in summary["note"] and summary["twins"] == 0


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
