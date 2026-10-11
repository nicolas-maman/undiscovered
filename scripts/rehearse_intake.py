"""Write a GitHub event for a valid describing result, so CI can rehearse the intake workflow.

    python scripts/rehearse_intake.py <distill-2025 checkout> event.json

The result is for the first open unit on the branch, made with the client's
own describe_body, with a description per paper that passes the client's
checks (no avoided word, no repeat). CI then runs the workflow's own
commands on it, against the live branch, without pushing anything, so a
broken workflow is found before a volunteer's result meets it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from undiscovered import cli, distill

LABELS = ["amber", "birch", "cobalt", "delta", "ember", "fennel", "garnet", "harbor", "indigo", "juniper",
          "kestrel", "lantern", "meadow", "nimbus", "orchid", "pebble", "quarry", "rowan", "saffron", "thistle"]


def main() -> None:
    branch, out = Path(sys.argv[1]), Path(sys.argv[2])
    index = json.loads((branch / "units" / "index.json").read_text(encoding="utf-8"))
    unit = next(u for u in index["units"] if u["status"] == "open")
    descs, taken = [], set()
    for i, w in enumerate(unit["works"]):
        d = {"problem": f"Find out how one quantity responds when another is changed, case {LABELS[i]}.",
             "approach": "Take repeated readings under steady conditions and compare them with a simple rule."}
        distill.check(d, unit["avoid"].get(w, []), unit["max_avoided"], taken)
        taken.add(distill.fingerprint(d))
        descs.append({"work": w, **d})
    body = cli.describe_body(unit, {"provider": "openai-compatible", "id": "rehearsal"}, descs)
    out.write_text(json.dumps({"issue": {"title": f"distill result {unit['unit']}", "body": body,
                                         "user": {"login": "ci-rehearsal"}, "number": 1}}), encoding="utf-8")
    print(f"rehearsal result for {unit['unit']}: {len(descs)} descriptions")


if __name__ == "__main__":
    main()
