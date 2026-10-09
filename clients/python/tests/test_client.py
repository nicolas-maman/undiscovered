"""Offline tests for the client: no network, no GitHub."""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import pytest

from undiscovered import cli, mapper, openalex
from undiscovered.stopwords import ENGLISH_STOP_WORDS

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "research"))


class FakeOpenAlex:
    """Answers the few queries a map unit makes, from canned data."""

    def __init__(self):
        self.remaining = 9000
        self.calls = []

    def get(self, path, params):
        self.calls.append(params)
        flt = params.get("filter", "")
        if params.get("group_by") == "publication_year":
            return {"group_by": [{"key": "2018", "count": 10}, {"key": "2025", "count": 30}]}
        if params.get("sample"):
            english = ("in this paper we show how it was done and why it is of some use to those who "
                       "are in the same place as we are and what we would do if we had to do it again")
            inverted = {}
            for i, w in enumerate(english.split()):
                inverted.setdefault(w, []).append(i)
            return {"results": [{"id": "W1", "title": "Sensor fusion", "abstract_inverted_index": inverted},
                                {"id": "W2", "title": "Short", "abstract_inverted_index": {"tiny": [0]}}]}
        if params.get("group_by") == "primary_topic.id":
            if "publication_year:<" in flt:
                return {"group_by": [{"key": "https://openalex.org/T9", "count": 2}]}
            return {"group_by": [{"key": "https://openalex.org/T7", "count": 5},
                                 {"key": "unknown", "count": 1}]}
        if params.get("sort") == "cited_by_count:desc":
            return {"results": [
                {"id": "https://openalex.org/W20", "cited_by_count": 900,
                 "counts_by_year": [{"year": 2026, "cited_by_count": 880}]},
                {"id": "https://openalex.org/W10", "cited_by_count": 300, "counts_by_year": []},
                {"id": "https://openalex.org/W30", "cited_by_count": 4,
                 "counts_by_year": [{"year": 2026, "cited_by_count": 4}]},
            ]}
        raise AssertionError(f"unexpected query {params}")

    def paged(self, path, params):
        yield self.get(path, params)


def test_stop_words_match_scikit_learn():
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    assert ENGLISH_STOP_WORDS == frozenset(sk.ENGLISH_STOP_WORDS)


def test_shared_rules_match_the_research_code():
    collect = pytest.importorskip("undiscovered_research.collect")
    embed = pytest.importorskip("undiscovered_research.embed")
    for name in ("TRAIN_YEARS", "RECENT_YEARS", "INSTRUMENT", "CANDIDATES", "ABSTRACTS", "SAMPLE_SEED"):
        assert getattr(mapper, name) == getattr(collect, name), name
    assert (mapper.MIN_WORDS, mapper.MIN_ENGLISH_SHARE) == (embed.MIN_WORDS, embed.MIN_ENGLISH_SHARE)
    rng = random.Random(0)
    vocab = sorted(ENGLISH_STOP_WORDS)[:60] + ["sensor", "graphene", "protein", "tax", "glacier"]
    for _ in range(200):
        text = " ".join(rng.choice(vocab) for _ in range(rng.randint(20, 80)))
        assert mapper.usable(text) == embed.usable(text)
    w = {"cited_by_count": 50, "counts_by_year": [{"year": 2019, "cited_by_count": 7}]}
    assert mapper.citations_up_to(w, 2017) == collect.citations_up_to(w, 2017) == 43


def test_a_map_record_has_everything_the_ranking_needs():
    api = FakeOpenAlex()
    rec = mapper.map_topic(api, "T1", 2025)
    assert rec["train_window"] == [2018, 2025] and rec["recent_window"] == [2023, 2025]
    # W20 is the most cited today, but almost all of that came in 2026, after the freeze.
    assert rec["instrument"] == ["W10", "W20"]               # W30 had no citations by 2025
    assert rec["size"] == 40 and rec["usable_abstracts"] == 1
    assert rec["cited_by_train"] == {"T7": 5} and rec["cited_by_before"] == {"T9": 2}
    assert "abstracts" not in rec                              # only the count is kept
    years = [c["filter"] for c in api.calls if "referenced_works" in c.get("filter", "")]
    assert any("publication_year:<2018" in f for f in years)  # every year before the window


def test_units_are_picked_at_random_and_never_twice():
    index = {"units": [{"unit": f"u-{i:06d}", "status": "open"} for i in range(5)] +
             [{"unit": "u-000099", "status": "done"}]}
    rng = random.Random(1)
    seen = {cli.pick_unit(index, {"u-000000", "u-000001"}, rng)["unit"] for _ in range(50)}
    assert seen <= {"u-000002", "u-000003", "u-000004"} and len(seen) > 1
    assert cli.pick_unit(index, {f"u-{i:06d}" for i in range(5)}, rng) is None


def test_a_dry_run_leaves_no_cache_behind(monkeypatch, tmp_path):
    made = []
    real = cli.tempfile.TemporaryDirectory

    def tracked(*a, **k):
        d = real(*a, **k)
        made.append(Path(d.name))
        return d

    monkeypatch.setattr(cli.tempfile, "TemporaryDirectory", tracked)
    monkeypatch.setattr(cli, "OpenAlex", lambda cache, key: FakeOpenAlex())
    content = cli.do_unit({"unit": "u-000001", "freeze": 2025, "topics": ["T1", "T2"]}, key="")
    data = json.loads(content)
    assert [r["topic"] for r in data["records"]] == ["T1", "T2"]
    assert made and not any(d.exists() for d in made)


def test_a_named_unit_is_submitted_once(monkeypatch):
    index = {"units": [{"unit": "u-000001", "status": "open", "freeze": 2025, "topics": ["T1"]}]}

    class Resp:
        def json(self):
            return index

    issues = []
    monkeypatch.setattr(cli.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(cli, "be_gentle", lambda: None)
    monkeypatch.setattr(cli, "do_unit", lambda unit, key: "{}")
    monkeypatch.setattr(cli.config, "load", lambda: {})
    monkeypatch.setattr(cli.config, "save", lambda cfg: None)
    monkeypatch.setattr(cli.github, "token", lambda: "token")
    monkeypatch.setattr(cli.github, "create_gist", lambda *a: "https://gist.github.com/someone/1")
    monkeypatch.setattr(cli.github, "open_issue", lambda *a: issues.append(a[2]) or "issue")
    cli.main(["work", "--unit", "u-000001", "--units", "3"])
    assert issues == ["map result u-000001"]


def test_the_submitted_result_follows_the_protocol():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO / "schemas" / "result.schema.json").read_text(encoding="utf-8"))
    body = cli.result_body({"unit": "u-000001"}, "https://gist.github.com/someone/0123456789abcdef0123",
                           hashlib.sha256(b"x").hexdigest())
    result = json.loads(body.split("```json\n")[1].split("\n```")[0])
    jsonschema.Draft202012Validator(schema).validate(result)


def test_the_openalex_key_never_reaches_the_cache(tmp_path, monkeypatch):
    sent = []

    class Resp:
        status_code = 200
        headers = {"X-RateLimit-Remaining": "77"}
        text = "{}"

        def json(self):
            return {"results": []}

    api = openalex.OpenAlex(tmp_path, key="SECRET")
    monkeypatch.setattr(openalex, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(api._session, "get", lambda url, params, timeout: sent.append(params) or Resp())
    api.get("works", {"filter": "publication_year:2025"})
    assert sent[0]["api_key"] == "SECRET" and api.remaining == 77
    assert not any(b"SECRET" in f.read_bytes() for f in tmp_path.rglob("*") if f.is_file())
    assert all("SECRET" not in str(f) for f in tmp_path.rglob("*"))


def test_a_map_record_follows_the_shared_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO / "schemas" / "map-record.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(mapper.map_topic(FakeOpenAlex(), "T1", 2025))
