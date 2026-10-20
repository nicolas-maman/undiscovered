"""Offline tests for describing units: making them, and checking what volunteers send back."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import distill_units  # noqa: E402
import intake  # noqa: E402
import units as map_units  # noqa: E402
from undiscovered import cli  # noqa: E402

GOOD = {"problem": "Measure how much of one small molecule a living tissue has built up, as a sign of thirst.",
        "approach": "React an extract with a reagent that colours that molecule, then read the colour."}


DISTINCT = [
    GOOD,
    {"problem": "Predict when the next shock comes after one has happened in the same place.",
     "approach": "Let each event raise the chance of others nearby for a while, and fit how fast that fades."},
    {"problem": "Rank teams fairly when they have played different opponents.",
     "approach": "Give each team a score that grows with the scores of the teams it beat, repeated until stable."},
    {"problem": "Follow a quantity that cannot be watched directly, using noisy readings that arrive over time.",
     "approach": "Keep a running estimate with its uncertainty and correct it a little with every new reading."},
    {"problem": "Tell which parts of a large assembly touch, without seeing it whole.",
     "approach": "Find pairs of positions that change together across many related examples."},
    {"problem": "Choose where to build a few depots so that every town is close to one.",
     "approach": "Start from a guess, move each depot to the middle of its towns, and repeat."},
]


def own(i: int) -> dict:
    """A description of the i-th paper, different from the others as real papers' descriptions are."""
    return DISTINCT[i]


def unit(works=("W1", "W2", "W3", "W4")) -> dict:
    return {"unit": "u-100001", "protocol": 0, "kind": "distill", "works": list(works),
            "avoid": {w: ["proline", "drought"] for w in works}, "max_avoided": 1,
            "instructions": distill_units.INSTRUCTIONS, "quorum": 2, "status": "open"}


def branch(tmp_path: Path, u: dict) -> Path:
    (tmp_path / "units").mkdir()
    (tmp_path / "units" / "index.json").write_text(json.dumps({"units": [u]}), encoding="utf-8")
    return tmp_path


def issue(u: dict, descs: list[dict] | None = None, model_id: str = "qwen3:8b") -> str:
    descs = descs if descs is not None else [{"work": w, **own(i)} for i, w in enumerate(u["works"])]
    return cli.describe_body(u, {"provider": "openai-compatible", "id": model_id}, descs)


def test_distinctive_words_are_the_fields_not_everyones():
    papers = {"W1": "Proline accumulates in leaves under drought stress. This paper measured proline perfectly.",
              "W2": "Glaciers retreat under warming. The study measured glacier mass.",
              "W3": "Banks lend under stress. The study measured lending."}
    domain = {"W1": "Life Sciences", "W2": "Physical Sciences", "W3": "Social Sciences"}
    common = {"perfectly", "leaves", "measured", "stress"}          # everyday English, for this test
    avoid = distill_units.distinctive(papers, domain, k=3, everyday=lambda w: 5.0 if w in common else 2.0)
    assert avoid["W1"] == ["proline", "accumulates", "drought"]
    assert avoid["W2"] == ["glacier", "glaciers", "mass"]
    assert all("perfectly" not in a and "paper" not in a and "study" not in a for a in avoid.values())


def test_a_common_word_counts_as_a_fields_when_its_papers_crowd_into_one_domain():
    counts = {f"W{i}": distill_units.Counter(["cancer"] if i < 12 else ["combined"]) for i in range(24)}
    counts.update({f"W{i}": distill_units.Counter(["combined"]) for i in range(12, 24)})
    domain = {f"W{i}": ("Health Sciences" if i < 12 else ["Life Sciences", "Physical Sciences",
                                                            "Social Sciences", "Health Sciences"][i % 4])
              for i in range(24)}
    words = distill_units.fields_words(counts, domain, everyday=lambda w: 5.0)
    assert "cancer" in words and "combined" not in words


def test_units_mix_papers_twenty_at_a_time_and_are_rebuilt_exactly():
    papers = {f"W{i}": {"topic": "T1", "domain": "Life Sciences"} for i in range(1, 46)}
    avoid = {w: ["x"] for w in papers}
    a, b = distill_units.make_units(papers, avoid), distill_units.make_units(papers, avoid)
    assert a == b and [len(u["works"]) for u in a["units"]] == [20, 20, 5]
    assert a["units"][0]["unit"] == "u-100001" and a["units"][0]["quorum"] == 2
    assert set(a["units"][0]["avoid"]) == set(a["units"][0]["works"])


def test_a_unit_is_complete_once_two_models_have_described_it(tmp_path):
    u = unit()
    d = branch(tmp_path, u)
    first = intake.intake_distill(d, issue(u), "alice", 11)
    assert "1 more model" in first and "qwen3:8b" in first
    for who, n in (("alice", 12), ("bob", 13)):          # the same model again, from anyone, adds nothing
        with pytest.raises(intake.Reject, match="needs another model"):
            intake.intake_distill(d, issue(u), who, n)
    second = intake.intake_distill(d, issue(u, model_id="llama3.1:8b"), "alice", 14)   # one person, two models
    assert "complete" in second
    saved = json.loads((d / "results" / "u-100001" / "14.json").read_text(encoding="utf-8"))
    assert saved["model"]["id"] == "llama3.1:8b" and saved["author"] == "alice" and len(saved["descriptions"]) == 4
    stored = json.loads((d / "units" / "index.json").read_text())["units"][0]
    assert stored["status"] == "done"
    assert stored["models"] == ["llama3.1:8b (openai-compatible)", "qwen3:8b (openai-compatible)"]


def test_a_template_filled_in_for_every_paper_is_rejected(tmp_path):
    u = unit()
    template = [{"work": w, "problem": f"Find out how one quantity responds when another is changed, case {c}.",
                 "approach": "Take repeated readings under steady conditions and compare them with a simple rule."}
                for w, c in zip(u["works"], ("amber", "birch", "cobalt", "delta"))]
    with pytest.raises(intake.Reject, match="W2: it said almost the same"):
        intake.intake_distill(branch(tmp_path, u), issue(u, template), "alice", 11)


def described(*works, **change) -> list[dict]:
    return [{"work": w, **own(i), **(change if i == 0 else {})} for i, w in enumerate(works)]


@pytest.mark.parametrize("descs,reason", [
    (described("W1", "W2", "W3", "W4", problem="Proline and drought, as the abstract says, in leaves."),
     "W1: it used words specific to the paper: proline, drought"),
    (described("W9", "W2", "W3", "W4"), "W9 is not one of the unit's papers"),
    (described("W1", "W1", "W3", "W4"), "described twice"),
    (described("W1", "W2"), "only 2 of the unit's 4"),
    (described("W1", "W2", "W3", "W4", approach="word " * 70), "longer than"),
    ([{"work": w, **GOOD} for w in ("W1", "W2", "W3", "W4")], "W2: it said almost the same"),
])
def test_bad_descriptions_are_rejected_with_the_reason(tmp_path, descs, reason):
    u = unit()
    with pytest.raises(intake.Reject, match=reason):
        intake.intake_distill(branch(tmp_path, u), issue(u, descs), "alice", 11)


def test_a_result_from_an_old_prompt_is_turned_away(tmp_path):
    u = unit()
    body = issue(u).replace('"prompt": 1', '"prompt": 0')
    with pytest.raises(intake.Reject, match="update the client"):
        intake.intake_distill(branch(tmp_path, u), body, "alice", 11)


def test_units_of_both_kinds_follow_the_unit_schema():
    from jsonschema import Draft202012Validator
    root = Path(__file__).resolve().parents[2]
    schema = Draft202012Validator(json.loads((root / "schemas" / "unit.schema.json").read_text(encoding="utf-8")))
    made = map_units.make_units([f"T{i}" for i in range(1, 25)], 2025)["units"]
    made += distill_units.make_units({f"W{i}": {} for i in range(1, 25)}, {f"W{i}": ["x"] for i in range(1, 25)})["units"]
    for u in made:
        assert not list(schema.iter_errors(u)), u["unit"]


def test_progress_counts_units_descriptions_people_and_models(tmp_path):
    u = unit()
    d = branch(tmp_path, u)
    intake.intake_distill(d, issue(u), "alice", 11)
    intake.intake_distill(d, issue(u, model_id="llama3.1:8b"), "bob", 13)
    p = json.loads((d / "progress.json").read_text(encoding="utf-8"))
    assert p["units"] == {"done": 1} and p["descriptions"] == 8 and p["papers_described"] == 4
    assert [c["login"] for c in p["contributors"]] == ["alice", "bob"]
    assert {m["id"]: m["units"] for m in p["models"]} == {"qwen3:8b": 1, "llama3.1:8b": 1}


def test_the_same_issue_processed_twice_is_stored_once(tmp_path):
    u = unit()
    d = branch(tmp_path, u)
    intake.intake_distill(d, issue(u), "alice", 11)
    assert "already stored" in intake.intake_distill(d, issue(u), "alice", 11)
    assert len(list((d / "results" / "u-100001").glob("*.json"))) == 1


def test_a_rejected_result_leaves_its_reason_on_the_branch(tmp_path, monkeypatch, capsys):
    u = unit()
    d = branch(tmp_path, u)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"issue": {"title": f"distill result {u['unit']}", "number": 21,
                                           "user": {"login": "carol"}, "body": issue(u, described("W1", "W2"))}}))
    monkeypatch.setenv("INTAKE_EVENT", str(event))
    monkeypatch.setenv("DISTILL_DIR", str(d))
    intake.main()
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    logged = json.loads((d / "rejected" / "21.json").read_text(encoding="utf-8"))
    assert not verdict["accepted"] and "only 2 of the unit's 4" in verdict["reply"]
    assert logged["reason"] in verdict["reply"] and logged["author"] == "carol" and logged["unit"] == u["unit"]
    assert logged["model"] == {"provider": "openai-compatible", "id": "qwen3:8b"}
