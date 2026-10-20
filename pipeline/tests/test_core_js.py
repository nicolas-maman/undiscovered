"""The browser client's rules (site/core.js) are the Python client's, case for case.

A result made in the browser is checked by the Python checking job, so the two
must agree on the prompt, on how an answer is parsed and on every check. Each
case below is run through both and the outcomes compared. Needs Node.
"""

import json
import pathlib
import shutil
import subprocess

import pytest

from undiscovered import distill

ROOT = pathlib.Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")

ANSWERS = [
    '{"problem": "Find which parts of a system act together.", "approach": "Count how often pairs of parts vary at once."}',
    'Sure! Here it is:\n```json\n{"problem": "Predict when the next event comes after one has happened.", '
    '"approach": "Let each event raise the chance of others nearby for a while."}\n```',
    '<think>{"problem": "x"}</think>{"problem": "Rank items by how many important items point at them.", '
    '"approach": "Repeat a weighted vote until the scores stop changing."}',
    '{"problem": "too short", "approach": "Estimate a hidden quantity from noisy readings as they arrive."}',
    '{"problem": "Estimate a hidden quantity from noisy readings.", "approach": 3}',
    "no json here",
    '{"problem": "Estimate a hidden quantity", "approach": "unterminated',
    '["problem", "approach"]',
    '{"problem": "  Spaces   and\nnew lines\tare   squashed  here. ", "approach": "And  here, too, in the approach."}',
]

AVOID_CASES = [
    ("Kalman filters estimate states; the filter updates.", ["filter", "Kalman", "state", "glacier"]),
    ("Les données sont analysées par réseaux.", ["données", "réseau", "analysées"]),
    ("Bus buses gas", ["bus", "gas", "gass"]),
    ("Its 3D model uses x² terms", ["3d", "x²", "model", "term"]),
]

DESCS = [
    ({"problem": "Find which parts of a system act together.",
      "approach": "Count how often pairs of parts vary at once."}, ["parts"], 2),
    ({"problem": "Kalman filter for the state of a grid.", "approach": "Kalman filter states updated as readings arrive."},
     ["kalman", "filter", "grid"], 2),
    ({"problem": " ".join(["word"] * 61), "approach": "Short approach here for the check."}, [], 2),
    ({"problem": "Find which parts of a system act together.", "approach": "Count how often pairs vary."}, [], 2),
    ({"problem": "Find which parts of the system act together!", "approach": "Count how often the pairs of parts vary at once."},
     [], 2),
    ({"problem": "Forecast a seasonal outbreak from weekly case counts.", "approach": "Update an estimate of the "
      "hidden state each week as new counts arrive."}, [], 2),
]

LIKENESS = [
    ("Find out how one quantity responds when another is changed, case amber. Take repeated readings under "
     "steady conditions and compare them with a simple rule.",
     "Find out how one quantity responds when another is changed, case birch. Take repeated readings under "
     "steady conditions and compare them with a simple rule."),
    ("Rank items by how many important items point at them.", "Forecast outbreaks from weekly counts."),
    ("the of and", "estimate a hidden state"),
    ("Données analysées données", "données"),
]


def run_js(cases: dict) -> dict:
    script = """
    const core = require(process.argv[1]);
    const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const out = {constants: {PROMPT: core.PROMPT, MAX_WORDS: core.MAX_WORDS, SYSTEM: core.SYSTEM, FORMAT: core.FORMAT,
                             SAME_SHAPE: core.SAME_SHAPE, STOP: Array.from(core.STOP).sort()}};
    out.likeness = cases.likeness.map(([a, b]) => core.likeness(a, b));
    out.parse = cases.answers.map(a => { try { return {ok: core.parse(a)}; } catch (e) { return {err: e.message}; } });
    out.avoided = cases.avoid.map(([t, a]) => core.avoided(t, a));
    out.check = cases.descs.map(([d, a, m]) => { try { core.check(d, a, m, new Set(cases.taken)); return {ok: true}; }
                                                 catch (e) { return {err: e.message}; } });
    out.fingerprint = cases.descs.map(([d]) => core.fingerprint(d));
    out.prompt = core.prompt(...cases.prompt);
    out.abstract = core.abstractText(cases.inverted);
    process.stdout.write(JSON.stringify(out));
    """
    done = subprocess.run([NODE, "-e", script, str(ROOT / "site" / "core.js")], input=json.dumps(cases),
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def python_outcome(fn, *args):
    try:
        return {"ok": fn(*args) if fn is not distill.check else (fn(*args) or True)}
    except distill.Unusable as e:
        return {"err": str(e)}


def test_browser_rules_are_the_python_rules():
    taken = [distill.fingerprint(DESCS[0][0])]
    prompt_args = ["Describe the problem.", "A title", "An abstract.", ["one", "two"]]
    inverted = {"Kalman": [0], "filters": [1, 4], "estimate": [2], "states": [3]}
    js = run_js({"answers": ANSWERS, "avoid": AVOID_CASES, "descs": DESCS, "taken": taken, "likeness": LIKENESS,
                 "prompt": prompt_args, "inverted": inverted})

    from undiscovered.stopwords import ENGLISH_STOP_WORDS
    assert js["constants"] == {"PROMPT": distill.PROMPT, "MAX_WORDS": distill.MAX_WORDS,
                               "SYSTEM": distill.SYSTEM, "FORMAT": distill.FORMAT,
                               "SAME_SHAPE": distill.SAME_SHAPE, "STOP": sorted(ENGLISH_STOP_WORDS)}
    assert js["likeness"] == pytest.approx([distill.likeness(a, b) for a, b in LIKENESS], abs=1e-12)
    assert js["likeness"][0] > distill.SAME_SHAPE > js["likeness"][1]
    assert js["parse"] == [python_outcome(distill.parse, a) for a in ANSWERS]
    assert js["avoided"] == [distill.avoided(t, a) for t, a in AVOID_CASES]
    assert js["check"] == [python_outcome(distill.check, d, a, m, set(taken)) for d, a, m in DESCS]
    assert js["fingerprint"] == [distill.fingerprint(d) for d, _, _ in DESCS]
    assert js["prompt"] == distill.prompt(*prompt_args)

    from undiscovered.openalex import abstract_text
    assert js["abstract"] == abstract_text(inverted)
