"""Write a GitHub event for a describing result, so CI can rehearse the intake workflow.

    python scripts/rehearse_intake.py <distill-2025 checkout> event.json          # a sound result
    python scripts/rehearse_intake.py <distill-2025 checkout> event.json junk     # one template for every paper

The result is for the first open unit on the branch, made with the client's
own describe_body. The sound one has a different plain description for each
paper that passes the client's checks; the junk one fills one template in for
every paper, which the checks must turn away. CI runs the workflow's own
commands on both, against the live branch, without pushing anything, so a
broken workflow, or one that lets junk in, is found before a volunteer's
result meets it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from undiscovered import cli, distill

LABELS = ["amber", "birch", "cobalt", "delta", "ember", "fennel", "garnet", "harbor", "indigo", "juniper",
          "kestrel", "lantern", "meadow", "nimbus", "orchid", "pebble", "quarry", "rowan", "saffron", "thistle"]

# Twenty plain descriptions of twenty different computations, one per paper.
SOUND = [
    ("Predict when the next shock comes after one has happened nearby.",
     "Let each event raise the chance of others close in place and time, and fit how fast that fades."),
    ("Rank competitors fairly when each has faced different opponents.",
     "Give each a score that grows with the scores of those it beat, and repeat until the scores settle."),
    ("Follow a hidden quantity using noisy readings that arrive one after another.",
     "Keep a running estimate with its uncertainty and correct it a little with every new reading."),
    ("Tell which parts of a large assembly touch each other without seeing it whole.",
     "Find pairs of positions that change together across many related examples."),
    ("Choose where to place a few depots so that every town is near one.",
     "Start from a guess, move each depot to the middle of the towns it serves, and repeat."),
    ("Recover a clear picture from far fewer measurements than usual.",
     "Assume most of the picture is empty and pick the sparsest picture that matches the measurements."),
    ("Estimate how strongly a treatment changes an outcome when groups were not assigned at random.",
     "Compare each treated case with untreated cases that looked the same beforehand."),
    ("Split a mixed collection into the groups it was drawn from.",
     "Guess the groups, assign each item to the likeliest one, update the groups, and repeat."),
    ("Find the most likely sequence of hidden states behind a series of observations.",
     "Step through the series keeping only the best path into each state, then trace it back."),
    ("Measure how fast something spreads outward from where it starts.",
     "Track how the spread of positions widens with time and fit the rate at which it grows."),
    ("Decide which of many inputs actually matter for an outcome.",
     "Fit a model that is penalised for every input it uses, so only the useful ones keep weight."),
    ("Forecast a value that rises and falls with a regular rhythm.",
     "Break the series into repeating cycles of different lengths and project the strongest ones forward."),
    ("Judge the ability of test takers from which questions they answered right.",
     "Model each answer as depending on the taker's ability and the question's difficulty, fitted together."),
    ("Explain why a few items gather most of the links in a growing network.",
     "Let each new item link to existing ones in proportion to how many links they already have."),
    ("Compare two collections of measurements by how much work it takes to turn one into the other.",
     "Find the cheapest way to move the amounts of one onto the other and report that cost."),
    ("Sample from a complicated distribution that cannot be written down in full.",
     "Propose small random moves and keep each with a probability that favours likelier states."),
    ("Find out whether two populations compete, cooperate or one feeds on the other.",
     "Write how each population's growth depends on the other's size and fit it to counts over time."),
    ("Assign texts to categories from the words they contain.",
     "Weigh each word by how much it separates the categories in labelled examples, then add the weights."),
    ("Fill in the missing entries of a large table from the entries that are known.",
     "Assume the table is made of a few underlying patterns and find the patterns that fit the known entries."),
    ("Detect a weak repeating signal buried in strong background noise.",
     "Match the data against a library of expected signal shapes and flag the best matches above chance."),
]


def main() -> None:
    branch, out = Path(sys.argv[1]), Path(sys.argv[2])
    junk = sys.argv[3:] == ["junk"]
    index = json.loads((branch / "units" / "index.json").read_text(encoding="utf-8"))
    unit = next(u for u in index["units"] if u["status"] == "open")
    descs, taken = [], set()
    for i, w in enumerate(unit["works"]):
        if junk:
            d = {"problem": f"Find out how one quantity responds when another is changed, case {LABELS[i]}.",
                 "approach": "Take repeated readings under steady conditions and compare them with a simple rule."}
        else:
            d = dict(zip(("problem", "approach"), SOUND[i]))
            distill.check(d, unit["avoid"].get(w, []), unit["max_avoided"], taken)
            taken.add(distill.fingerprint(d))
        descs.append({"work": w, **d})
    body = cli.describe_body(unit, {"provider": "openai-compatible", "id": "rehearsal"}, descs)
    out.write_text(json.dumps({"issue": {"title": f"distill result {unit['unit']}", "body": body,
                                         "user": {"login": "ci-rehearsal"},
                                         "number": 2 if junk else 1}}), encoding="utf-8")
    print(f"rehearsal {'junk' if junk else 'sound'} result for {unit['unit']}: {len(descs)} descriptions")


if __name__ == "__main__":
    main()
