"""Offline tests for the project's side: making units and checking results."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import intake  # noqa: E402
import units  # noqa: E402


def record(topic: str, freeze: int = 2025) -> dict:
    by_year = {str(y): 10 for y in range(freeze - 7, freeze + 1)}
    return {"format": 1, "topic": topic, "freeze": freeze, "retrieved": "2026-10-09",
            "train_window": [freeze - 7, freeze], "recent_window": [freeze - 2, freeze],
            "size": sum(by_year.values()), "works_by_year": by_year,
            "instrument": [f"W{i}" for i in range(1, 101)], "usable_abstracts": 33,
            "cited_by_train": {"T7": 50, "T8": 3}, "cited_by_recent": {"T7": 20},
            "cited_by_before": {"T9": 4}}


def payload(unit: dict, records: list[dict] | None = None) -> tuple[str, str]:
    content = json.dumps({"unit": unit["unit"], "freeze": unit["freeze"],
                          "records": records if records is not None else [record(t) for t in unit["topics"]]},
                         sort_keys=True, separators=(",", ":"))
    return content, hashlib.sha256(content.encode()).hexdigest()


def body(unit_id: str, sha: str, gist: str = "https://gist.github.com/someone/0123456789abcdef0123") -> str:
    result = {"unit": unit_id, "protocol": 0, "client": {"name": "undiscovered-py", "version": "0.1.0"},
              "gist": gist, "sha256": sha}
    return "text\n```json\n" + json.dumps(result, indent=1) + "\n```\n"


def unit_needing_check(want: bool) -> str:
    return next(f"u-{i:06d}" for i in range(1, 10_000) if intake.needs_check(f"u-{i:06d}") == want)


@pytest.fixture
def branch(tmp_path):
    ids = {"plain": unit_needing_check(False), "checked": unit_needing_check(True)}
    index = {"freeze": 2025, "units": [
        {"unit": ids["plain"], "kind": "map", "topics": ["T1", "T2"], "freeze": 2025, "quorum": 1, "status": "open"},
        {"unit": ids["checked"], "kind": "map", "topics": ["T3"], "freeze": 2025, "quorum": 1, "status": "open"}]}
    (tmp_path / "units").mkdir()
    (tmp_path / "units" / "index.json").write_text(json.dumps(index))
    return tmp_path, index, ids


def status(map_dir: Path, unit_id: str) -> str:
    index = json.loads((map_dir / "units" / "index.json").read_text())
    return next(u["status"] for u in index["units"] if u["unit"] == unit_id)


def test_units_cover_every_topic_once_and_are_reproducible():
    ids = [f"T{10000 + i}" for i in range(4516)]
    a, b = units.make_units(ids, 2025), units.make_units(list(reversed(ids)), 2025)
    assert a == b and len(a["units"]) == 452
    flat = [t for u in a["units"] for t in u["topics"]]
    assert sorted(flat) == sorted(ids) and max(len(u["topics"]) for u in a["units"]) == 10


def test_about_one_unit_in_twenty_is_checked():
    share = sum(intake.needs_check(f"u-{i:06d}") for i in range(1, 4001)) / 4000
    assert 0.03 < share < 0.07


def test_a_sound_result_is_accepted_and_stored(branch):
    map_dir, index, ids = branch
    unit = index["units"][0]
    content, sha = payload(unit)
    reply = intake.intake(map_dir, body(unit["unit"], sha), "alice", 7, fetch=lambda url, tok: content)
    assert reply.startswith("Accepted") and status(map_dir, unit["unit"]) == "done"
    assert json.loads((map_dir / "records" / "T1.json").read_text())["topic"] == "T1"
    assert json.loads((map_dir / "results" / f"{unit['unit']}.json").read_text())[0]["author"] == "alice"
    again = intake.intake(map_dir, body(unit["unit"], sha), "bob", 8, fetch=lambda url, tok: content)
    assert "already complete" in again


@pytest.mark.parametrize("break_it, message", [
    (lambda recs: recs[0].update(train_window=[2017, 2025]), "wrong windows"),
    (lambda recs: recs[0].update(size=1), "size is not the sum"),
    (lambda recs: recs[0].update(instrument=["not-an-id"]), "reference papers"),
    (lambda recs: recs[0].update(usable_abstracts=41), "usable_abstracts"),
    (lambda recs: recs[0]["cited_by_train"].update({"T1": -2}), "cited_by_train"),
    (lambda recs: recs.reverse(), "exactly the unit's topics"),
])
def test_bad_records_are_rejected(branch, break_it, message):
    map_dir, index, ids = branch
    unit = index["units"][0]
    recs = [record(t) for t in unit["topics"]]
    break_it(recs)
    content, sha = payload(unit, recs)
    with pytest.raises(intake.Reject, match=message):
        intake.intake(map_dir, body(unit["unit"], sha), "alice", 7, fetch=lambda url, tok: content)
    assert status(map_dir, unit["unit"]) == "open"


def test_a_checksum_mismatch_or_odd_issue_is_rejected(branch):
    map_dir, index, ids = branch
    unit = index["units"][0]
    content, sha = payload(unit)
    with pytest.raises(intake.Reject, match="checksum"):
        intake.intake(map_dir, body(unit["unit"], "0" * 64), "alice", 7, fetch=lambda url, tok: content)
    with pytest.raises(intake.Reject, match="no JSON block"):
        intake.intake(map_dir, "just words", "alice", 7, fetch=lambda url, tok: content)
    with pytest.raises(intake.Reject, match="gist"):
        intake.intake(map_dir, body(unit["unit"], sha, gist="https://evil.example/x"), "alice", 7,
                      fetch=lambda url, tok: content)


def test_a_checked_unit_needs_a_second_volunteer_who_agrees(branch):
    map_dir, index, ids = branch
    unit = index["units"][1]
    content, sha = payload(unit)
    intake.intake(map_dir, body(unit["unit"], sha), "alice", 7, fetch=lambda url, tok: content)
    assert status(map_dir, unit["unit"]) == "check"
    with pytest.raises(intake.Reject, match="another volunteer"):
        intake.intake(map_dir, body(unit["unit"], sha), "alice", 8, fetch=lambda url, tok: content)
    drift = [copy.deepcopy(record(t)) for t in unit["topics"]]
    drift[0]["cited_by_train"]["T7"] = 51                          # a live index moves a little
    c2, s2 = payload(unit, drift)
    reply = intake.intake(map_dir, body(unit["unit"], s2), "bob", 9, fetch=lambda url, tok: c2)
    assert "agree" in reply and status(map_dir, unit["unit"]) == "done"


def test_a_second_result_that_disagrees_sets_the_unit_aside(branch):
    map_dir, index, ids = branch
    unit = index["units"][1]
    content, sha = payload(unit)
    intake.intake(map_dir, body(unit["unit"], sha), "alice", 7, fetch=lambda url, tok: content)
    wrong = [record(t) for t in unit["topics"]]
    wrong[0]["instrument"] = [f"W{i}" for i in range(500, 600)]
    c2, s2 = payload(unit, wrong)
    intake.intake(map_dir, body(unit["unit"], s2), "bob", 9, fetch=lambda url, tok: c2)
    assert status(map_dir, unit["unit"]) == "disputed"
