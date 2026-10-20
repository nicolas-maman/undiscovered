"""Write a GitHub event for a describing result, so CI can rehearse the intake workflow.

    python scripts/rehearse_intake.py <distill-2025 checkout> event.json          # a sound result
    python scripts/rehearse_intake.py <distill-2025 checkout> event.json junk     # one template for every paper

The result is for the first open unit on the branch, made with the client's
own describe_body. The sound one describes each paper with words from its
own abstract (fetched from OpenAlex as a client fetches it), less the words
the unit says to avoid, so it passes the checks; the junk one fills one
template in for every paper, which the checks must turn away. CI runs the workflow's own
commands on both, against the live branch, without pushing anything, so a
broken workflow, or one that lets junk in, is found before a volunteer's
result meets it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tempfile

from undiscovered import cli, distill
from undiscovered.openalex import OpenAlex

LABELS = ["amber", "birch", "cobalt", "delta", "ember", "fennel", "garnet", "harbor", "indigo", "juniper",
          "kestrel", "lantern", "meadow", "nimbus", "orchid", "pebble", "quarry", "rowan", "saffron", "thistle"]



def from_abstract(abstract: str, avoid: list[str]) -> dict[str, str] | None:
    """A crude description made of the abstract's own words, without the avoided ones."""
    banned = {distill._stem(a.lower()) for a in avoid}
    words = [w for w in distill.WORD.findall(abstract) if distill._stem(w.lower()) not in banned]
    if len(words) < 30:
        return None
    return {"problem": " ".join(words[:20]) + ".", "approach": " ".join(words[20:40]) + "."}


def main() -> None:
    branch, out = Path(sys.argv[1]), Path(sys.argv[2])
    junk = sys.argv[3:] == ["junk"]
    index = json.loads((branch / "units" / "index.json").read_text(encoding="utf-8"))
    unit = next(u for u in index["units"] if u["status"] == "open")
    descs, taken = [], set()
    if not junk:            # the papers' own abstracts, fetched as a client fetches them
        with tempfile.TemporaryDirectory() as tmp:
            works = distill.fetch_works(OpenAlex(Path(tmp), ""), unit["works"])
    for i, w in enumerate(unit["works"]):
        if junk:
            d = {"problem": f"Find out how one quantity responds when another is changed, case {LABELS[i]}.",
                 "approach": "Take repeated readings under steady conditions and compare them with a simple rule."}
        else:
            d = from_abstract(works.get(w, {}).get("abstract", ""), unit["avoid"].get(w, []))
            if d is None:
                continue
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
