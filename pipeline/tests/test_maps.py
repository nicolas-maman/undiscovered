"""Offline tests for the site's two maps of the describing set."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

pytest.importorskip("sklearn")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maps  # noqa: E402

TOPICS = {"Life Sciences": ["enzyme", "membrane", "protein", "gene", "cell", "tissue"],
          "Physical Sciences": ["lattice", "crystal", "laser", "orbit", "plasma", "wave"]}


def branch(tmp_path: Path, described: int = 0) -> Path:
    rng = random.Random(3)
    papers, lines, index = {}, [], []
    for i in range(80):
        domain = "Life Sciences" if i % 2 == 0 else "Physical Sciences"
        w = f"W{i}"
        papers[w] = {"domain": domain, "field": domain.split()[0]}
        words = rng.choices(TOPICS[domain], k=12)
        lines.append(json.dumps({"work": w, "title": f"Paper {i}", "year": 2024, "abstract": " ".join(words)}))
        if i < described:
            index.append(json.dumps({"work": w, "descriptions": [
                {"problem": "estimate a hidden quantity " + " ".join(rng.choices(["noise", "signal", "rate"], k=4)),
                 "approach": "update the estimate as readings arrive"}]}))
    (tmp_path / "papers.json").write_text(json.dumps(papers))
    (tmp_path / "abstracts.jsonl").write_text("\n".join(lines))
    if index:
        (tmp_path / "combined").mkdir()
        (tmp_path / "combined" / "descriptions.jsonl").write_text("\n".join(index))
    return tmp_path


def test_the_abstract_map_places_every_paper_and_is_reused_while_the_set_is_unchanged(tmp_path):
    b = branch(tmp_path)
    assert maps.maps(b) == {"papers": 80, "described": 0, "description_map": False}
    first = json.loads((b / "combined" / "map.json").read_text())
    xy = first["layouts"]["abstracts"]
    assert len(xy) == 80 and all(0 <= c <= maps.SCALE for p in xy for c in p)
    assert first["layouts"]["descriptions"] == [None] * 80
    assert first["papers"][0][:2] == ["W0", first["fields"].index("Life")]
    maps.maps(b)
    assert json.loads((b / "combined" / "map.json").read_text())["layouts"]["abstracts"] == xy


def test_described_papers_get_a_place_on_the_description_map(tmp_path):
    b = branch(tmp_path, described=60)
    assert maps.maps(b)["description_map"]
    out = json.loads((b / "combined" / "map.json").read_text())
    placed = [p for p in out["layouts"]["descriptions"] if p is not None]
    assert len(placed) == 60 and out["described"] == 60
