"""The robustness checks of research/PREREGISTRATION.md, in one run.

    python -m undiscovered_research.robustness [--second-sample data_seed2027]

Runs the main analysis and each preregistered variation, and writes
``results/robustness.json``. The checks are reported next to the main
result and do not change the decision. Check 5 of the plan (results by
domain pair) is part of every report already.

The second sample needs its own collection first:

    python -m undiscovered_research.collect --seed 2027 --data data_seed2027
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import backtest, collect, embed

MAIN_MODEL = "BAAI/bge-small-en-v1.5"

# (key, what changes, settings) in the order of the plan's list.
# The main run: connected at 3 or more citing works, unconnected at most one
# before the cutoff, bge-small embeddings, topics drawn with seed 2026.
VARIANTS = [
    ("main", "As planned", {}),
    ("k2", "Connected at 2+ citing works", {"min_test_links": 2}),
    ("k5", "Connected at 5+ citing works", {"min_test_links": 5}),
    ("e0", "No link at all up to 2017", {"max_prior_links": 0}),
    ("bge_base", "Embeddings: bge-base", {"model": "BAAI/bge-base-en-v1.5"}),
    ("seed2027", "Other 300 topics (seed 2027)", {"second_sample": True}),
]


def summarise(report: dict) -> dict:
    """The part of a report that a robustness table needs."""
    return {
        "pairs": report["pairs"],
        "models": {name: {"average_precision": m["average_precision"],
                          "average_precision_ci": m.get("average_precision_ci")}
                   for name, m in report["models"].items()},
        "hypotheses": report["hypotheses"],
        "decision": report["decision"],
    }


def _use_data(path: Path) -> None:
    backtest.DATA = collect.DATA = embed.DATA = path


def run(second_sample: Path | None) -> dict:
    default = backtest.DATA
    out = {"variants": []}
    try:
        for key, label, settings in VARIANTS:
            entry = {"key": key, "label": label}
            if settings.get("second_sample"):
                if not second_sample or not (second_sample / "sample.json").exists():
                    entry["skipped"] = "the second sample has not been collected"
                    out["variants"].append(entry)
                    continue
                _use_data(second_sample)
            report = backtest.run(settings.get("max_prior_links", 1),
                                  settings.get("min_test_links", 3),
                                  settings.get("model", MAIN_MODEL))
            _use_data(default)
            entry.update(summarise(report))
            out["variants"].append(entry)
            if key == "main":
                out["main"] = report
            print(f"{key}: H1 diff {report['hypotheses']['H1_combined_beats_network']['diff']:+.4f} "
                  f"{report['hypotheses']['H1_combined_beats_network']['diff_ci']}", flush=True)
    finally:
        _use_data(default)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--second-sample", default="data_seed2027",
                    help="data directory of the seed-2027 sample (relative to research/)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    second = Path(args.second_sample)
    if not second.is_absolute():
        second = backtest.DATA.parent / second
    result = run(second.resolve())
    backtest.RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else backtest.RESULTS / "robustness.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
