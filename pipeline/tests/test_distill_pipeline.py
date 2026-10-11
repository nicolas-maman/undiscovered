"""Offline tests for describing units: making them, and checking what volunteers send back."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import distill_units  # noqa: E402
import intake  # noqa: E402
from undiscovered import cli  # noqa: E402

GOOD = {"problem": "Measure how much of one small molecule a living tissue has built up, as a sign of thirst.",
        "approach": "React an extract with a reagent that colours that molecule, then read the colour."}


def unit(works=("W1", "W2", "W3", "W4")) -> dict:
    return {"unit": "u-100001", "protocol": 0, "kind": "distill", "works": list(works),
            "avoid": {w: ["proline", "drought"] for w in works}, "max_avoided": 1,
            "instructions": distill_units.INSTRUCTIONS, "quorum": 2, "status": "open"}


def branch(tmp_path: Path, u: dict) -> Path:
    (tmp_path / "units").mkdir()
    (tmp_path / "units" / "index.json").write_text(json.dumps({"units": [u]}), encoding="utf-8")
    return tmp_path


def issue(u: dict, descs: list[dict] | None = None, model_id: str = "qwen3:8b") -> str:
    descs = descs if descs is not None else [{"work": w, **GOOD} for w in u["works"]]
    return cli.describe_body(u, {"provider": "openai-compatible", "id": model_id}, descs)


def test_distinctive_words_are_the_papers_own_not_everyones():
    papers = {"W1": "Proline accumulates in leaves under drought stress. The study measured proline.",
              "W2": "Glaciers retreat under warming. The study measured glacier mass.",
              "W3": "Banks lend under stress. The study measured lending."}
    avoid = distill_units.distinctive(papers, k=2)
    assert avoid["W1"][0] == "proline" and avoid["W2"] == ["glacier", "glaciers"]
    assert all("study" not in a and "measured" not in a for a in avoid.values())   # in every paper


def test_units_mix_papers_twenty_at_a_time_and_are_rebuilt_exactly():
    papers = {f"W{i}": {"topic": "T1", "domain": "Life Sciences"} for i in range(1, 46)}
    avoid = {w: ["x"] for w in papers}
    a, b = distill_units.make_units(papers, avoid), distill_units.make_units(papers, avoid)
    assert a == b and [len(u["works"]) for u in a["units"]] == [20, 20, 5]
    assert a["units"][0]["unit"] == "u-100001" and a["units"][0]["quorum"] == 2
    assert set(a["units"][0]["avoid"]) == set(a["units"][0]["works"])


def test_two_volunteers_complete_a_unit(tmp_path):
    u = unit()
    d = branch(tmp_path, u)
    first = intake.intake_distill(d, issue(u), "alice", 11)
    assert "needs 1 more" in first and "qwen3:8b" in first
    with pytest.raises(intake.Reject, match="once"):
        intake.intake_distill(d, issue(u), "alice", 12)
    second = intake.intake_distill(d, issue(u, model_id="llama3.1:8b"), "bob", 13)
    assert "complete" in second
    saved = json.loads((d / "results" / "u-100001" / "13.json").read_text(encoding="utf-8"))
    assert saved["model"]["id"] == "llama3.1:8b" and saved["author"] == "bob" and len(saved["descriptions"]) == 4
    assert json.loads((d / "units" / "index.json").read_text())["units"][0]["status"] == "done"


def described(*works, **change) -> list[dict]:
    return [{"work": w, **GOOD, **(change if i == 0 else {})} for i, w in enumerate(works)]


@pytest.mark.parametrize("descs,reason", [
    (described("W1", "W2", "W3", "W4", problem="Proline and drought, as the abstract says, in leaves."),
     "W1: it used words specific to the paper: proline, drought"),
    (described("W9", "W2", "W3", "W4"), "W9 is not one of the unit's papers"),
    (described("W1", "W1", "W3", "W4"), "described twice"),
    (described("W1", "W2"), "only 2 of the unit's 4"),
    (described("W1", "W2", "W3", "W4", approach="word " * 70), "longer than"),
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
