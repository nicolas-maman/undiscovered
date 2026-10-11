"""Offline tests for describing papers and for the model connections: no network, no model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from undiscovered import cli, distill, models

REPO = Path(__file__).resolve().parents[3]
INSTRUCTIONS = "Describe the problem and the approach without the field's words."


class FakeAPI:
    def __init__(self):
        self.calls = []

    def get(self, path, params):
        self.calls.append(params)
        return {"results": [
            {"id": "https://openalex.org/W1", "title": "Proline in drought",
             "abstract_inverted_index": {"Leaves": [0], "accumulate": [1], "proline": [2],
                                         "under": [3], "drought": [4]}},
            {"id": "https://openalex.org/W2", "title": "No abstract", "abstract_inverted_index": None},
        ]}


class FakeModel:
    """Answers from a list, one per question, and records the questions."""

    def __init__(self, answers):
        self.answers, self.asked, self.id = list(answers), [], "fake"
        self.provenance = {"provider": "openai-compatible", "id": "fake"}

    def ask(self, system, user):
        self.asked.append(user)
        return self.answers.pop(0)


GOOD = json.dumps({"problem": "Measure how much of one small molecule a living tissue has built up.",
                   "approach": "React an extract with a reagent that colours that molecule and read the colour."})


def test_the_abstract_is_rebuilt_in_word_order():
    assert distill.abstract_text({"b": [1], "a": [0, 2]}) == "a b a"
    assert distill.abstract_text(None) == ""


def test_answers_wrapped_in_text_or_thinking_are_read():
    wrapped = "<think>first I consider { odd } things</think>Sure! " + GOOD + " Hope this helps."
    assert distill.parse(wrapped)["problem"].startswith("Measure")
    for bad in ("no json here", '{"problem": "x"}', '{"problem": 3, "approach": "a b c d e"}'):
        with pytest.raises(distill.Unusable):
            distill.parse(bad)


def test_the_papers_own_words_are_counted_ignoring_case_and_plural():
    assert distill.avoided("Proline levels in LEAVES", ["proline", "leave", "drought"]) == ["proline", "leave"]
    desc = {"problem": "proline and drought matter here", "approach": "we look at them closely"}
    distill.check(desc, ["proline", "drought"], max_avoided=2)
    with pytest.raises(distill.Unusable, match="specific to the paper: proline, drought"):
        distill.check(desc, ["proline", "drought"], max_avoided=1)
    with pytest.raises(distill.Unusable, match="longer than"):
        distill.check({"problem": "word " * 61, "approach": "a b c d"}, [], 2)


def test_a_failed_answer_is_retried_once_with_the_reason():
    model = FakeModel(["not json", GOOD])
    desc = distill.describe(model, INSTRUCTIONS, {"title": "T", "abstract": "A"}, ["proline"], 1)
    assert desc["approach"].startswith("React")
    assert "could not be used: the answer was not a JSON object" in model.asked[1]
    assert "Do not use these words, which are specific to this paper: proline." in model.asked[0]


def test_a_unit_skips_works_without_an_abstract_and_keeps_its_order():
    api, model = FakeAPI(), FakeModel([GOOD])
    unit = {"unit": "u-100000", "works": ["W1", "W2"], "instructions": INSTRUCTIONS,
            "avoid": {"W1": ["proline", "drought"]}, "max_avoided": 1}
    out = distill.distill_unit(api, model, unit)
    assert [d["work"] for d in out] == ["W1"]
    assert api.calls == [{"filter": "openalex:W1|W2", "per_page": 2, "select": "id,title,abstract_inverted_index"}]


def test_a_model_that_keeps_failing_is_stopped_before_anything_is_sent():
    unit = {"unit": "u-100000", "works": ["W1"], "instructions": INSTRUCTIONS}
    with pytest.raises(distill.Unusable, match="failed the checks for 1 of 1"):
        distill.distill_unit(FakeAPI(), FakeModel(["nope", "still nope"]), unit)


def test_the_result_follows_the_protocol():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO / "schemas" / "result.schema.json").read_text(encoding="utf-8"))
    body = cli.describe_body({"unit": "u-100000"}, {"provider": "openai-compatible", "id": "fake"},
                             [{"work": "W1", **json.loads(GOOD)}])
    result = json.loads(body.split("```json\n")[1].split("\n```")[0])
    jsonschema.Draft202012Validator(schema).validate(result)
    assert result["prompt"] == distill.PROMPT and len(body) < 65536


@pytest.mark.parametrize("provider,url,answer", [
    ("openai-compatible", "http://127.0.0.1:11434/v1/chat/completions",
     {"choices": [{"message": {"content": "hi"}}]}),
    ("anthropic", "https://api.anthropic.com/v1/messages", {"content": [{"type": "text", "text": "hi"}]}),
    ("google", "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent",
     {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}),
])
def test_each_kind_of_endpoint_is_asked_at_temperature_zero(monkeypatch, provider, url, answer):
    sent = []

    class Resp:
        status_code = 200

        def json(self):
            return answer

    base = models.LOCAL["Ollama"] if provider == "openai-compatible" else ""
    m = models.Model(provider, "m", base, key="SECRET")
    monkeypatch.setattr(m._session, "post", lambda u, headers, json, timeout: sent.append((u, headers, json)) or Resp())
    assert m.ask("sys", "user") == "hi"
    u, headers, body = sent[0]
    assert u == url
    temperature = body.get("temperature", body.get("generationConfig", {}).get("temperature"))
    assert temperature == 0
    assert "SECRET" in json.dumps(headers) and "SECRET" not in json.dumps(body) + u
    assert m.provenance == {"provider": provider, "id": "m"}


def test_no_model_is_chosen_until_the_volunteer_chooses_one():
    assert models.from_settings({}) is None
    with pytest.raises(models.ModelError):
        models.Model("openai-compatible", "m")          # no base URL
    with pytest.raises(models.ModelError):
        models.Model("someone-else", "m", "http://x")


def test_environment_variables_override_the_settings_file(monkeypatch):
    cfg = {"model": {"provider": "openai-compatible", "base_url": "http://a/v1", "id": "small", "key": "k1"}}
    monkeypatch.setenv("UNDISCOVERED_MODEL", "large")
    monkeypatch.setenv("UNDISCOVERED_MODEL_KEY", "k2")
    m = models.from_settings(cfg)
    assert (m.base, m.id, m.key) == ("http://a/v1", "large", "k2")
    monkeypatch.setenv("UNDISCOVERED_MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("UNDISCOVERED_MODEL_BASE_URL", "")
    assert models.from_settings({"model": {"id": "x"}}).base == models.BASE["anthropic"]


def test_too_many_requests_waits_as_told_and_slows_down(monkeypatch):
    slept, replies = [], []

    class Resp:
        def __init__(self, status, headers=None):
            self.status_code, self.headers, self.text = status, headers or {}, ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    replies += [Resp(429, {"Retry-After": "7"}), Resp(429), Resp(200)]
    m = models.Model("openai-compatible", "m", "http://a/v1")
    monkeypatch.setattr(models.time, "sleep", slept.append)
    monkeypatch.setattr(m._session, "post", lambda *a, **k: replies.pop(0))
    assert m.ask("s", "u") == "ok"
    assert slept[0] == 7.0                       # the server's own Retry-After
    assert m.interval == 4.0                     # 2 s after the first 429, doubled after the second
