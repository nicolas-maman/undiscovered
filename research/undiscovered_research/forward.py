"""The forward test (research/FORWARD-TEST-DRAFT.md): its data.

    python -m undiscovered_research.forward collect     # the 300 topics at the end of 2025

Each topic's record is made by the volunteer client's own code
(clients/python, ``mapper.map_topic``), so the forward test ranks exactly
what a map unit would record. Records go to ``research/data_forward``, one
file per topic; a topic already there is not asked for again, so the
command can be run once a day until it reports every topic done. Nothing in
it looks at any outcome: the citations the forward test is scored on have
not been written yet.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .gentle import be_gentle

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH.parent / "clients" / "python"))
from undiscovered import mapper  # noqa: E402
from undiscovered.openalex import BudgetExhausted, OpenAlex  # noqa: E402

FREEZE = 2025
SAMPLE = RESEARCH / "data" / "sample.json"          # the first test's 300 topics
OUT = RESEARCH / "data_forward"


def key() -> str:
    path = RESEARCH / ".openalex_key"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def collect(out: Path = OUT, sample: Path = SAMPLE) -> int:
    """Record every topic not yet recorded. Returns how many are still missing."""
    topics = [t["id"] for t in json.loads(sample.read_text(encoding="utf-8"))]
    (out / "records").mkdir(parents=True, exist_ok=True)
    todo = [t for t in topics if not (out / "records" / f"{t}.json").exists()]
    print(f"{len(topics) - len(todo)} of {len(topics)} topics recorded at the end of {FREEZE}")
    with tempfile.TemporaryDirectory(prefix="undiscovered-forward-") as tmp:
        api = OpenAlex(Path(tmp), key())
        for i, t in enumerate(todo, 1):
            try:
                rec = mapper.map_topic(api, t, FREEZE)
            except BudgetExhausted as e:
                print(f"stopped: {e}; run the same command again after it resets")
                break
            path = out / "records" / f"{t}.json"
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
            tmp_path.replace(path)
            left = f" (OpenAlex calls left today: {api.remaining})" if api.remaining is not None else ""
            print(f"{i}/{len(todo)} {t}{left}", flush=True)
    missing = sum(not (out / "records" / f"{t}.json").exists() for t in topics)
    print("every topic recorded" if not missing else f"{missing} topics still to record")
    return missing


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["collect"])
    args = ap.parse_args()
    be_gentle()
    if args.step == "collect":
        collect()


if __name__ == "__main__":
    main()
