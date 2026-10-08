"""The robustness checks of research/PREREGISTRATION.md, in one run.

    python -m undiscovered_research.backtest                 # the main analysis first
    python -m undiscovered_research.robustness [--second-sample data_seed2027]

Takes the main report from ``results/``, reruns H1 under each variation the
plan lists, and writes ``results/robustness.json``. The checks are reported
next to the main result and do not change the decision. Results by domain
pair, also in the plan, are part of every report already.

The second sample needs its own collection first:

    python -m undiscovered_research.collect --seed 2027 --data data_seed2027
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import backtest, collect, embed
from .gentle import be_gentle

MAIN_MODEL = embed.TFIDF
MAIN_REPORT = "backtest_e1_k3_tfidf.json"

# (key, what changes, settings) in the order of the plan's list. The main
# run: connected at 3 or more citing works, unconnected at most one before
# the cutoff, TF-IDF content vectors, topics drawn with seed 2026.
VARIANTS = [
    ("k2", "Connected at 2+ citing works", {"min_test_links": 2}),
    ("k5", "Connected at 5+ citing works", {"min_test_links": 5}),
    ("e0", "No link at all up to 2017", {"max_prior_links": 0}),
    ("large", "Topics with 200+ works only", {"min_size": 200}),
    ("bge_small", "Pretrained embeddings: bge-small", {"model": "BAAI/bge-small-en-v1.5"}),
    ("bge_base", "Pretrained embeddings: bge-base", {"model": "BAAI/bge-base-en-v1.5"}),
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
    }


def _use_data(path: Path) -> None:
    backtest.DATA = collect.DATA = embed.DATA = path


def run(main_report: dict, second_sample: Path | None,
        n_boot: int = backtest.BOOTSTRAP_ROBUSTNESS) -> dict:
    default = backtest.DATA
    out = {"variants": [{"key": "main", "label": "As planned", **summarise(main_report)}]}
    strict = main_report.get("strict")
    if strict:
        out["variants"].append({
            "key": "strict", "label": "Stricter label (no possibly misfiled papers)",
            "pairs": {**main_report["pairs"], "eval_positive": strict["positive"]},
            "hypotheses": {"H1_combined_beats_network": {
                "diff": strict["diff"], "diff_ci": strict["diff_ci"],
                "holds": strict["diff_ci"][0] > 0}}})
    try:
        for key, label, settings in VARIANTS:
            entry = {"key": key, "label": label}
            if settings.get("second_sample"):
                if not second_sample or not (second_sample / "sample.json").exists():
                    entry["skipped"] = "the second sample has not been collected"
                    out["variants"].append(entry)
                    continue
                _use_data(second_sample)
            try:
                report = backtest.run(settings.get("max_prior_links", 1),
                                      settings.get("min_test_links", 3),
                                      settings.get("model", MAIN_MODEL),
                                      n_boot=n_boot, min_size=settings.get("min_size", 0))
            except backtest.NotEnoughData as e:
                entry["skipped"] = str(e)
                out["variants"].append(entry)
                continue
            finally:
                _use_data(default)
            entry.update(summarise(report))
            out["variants"].append(entry)
            h1 = report["hypotheses"]["H1_combined_beats_network"]
            print(f"{key}: H1 diff {h1['diff']:+.4f} {h1['diff_ci']}", flush=True)
    finally:
        _use_data(default)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--second-sample", default="data_seed2027",
                    help="data directory of the seed-2027 sample (relative to research/)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    be_gentle()
    main_path = backtest.RESULTS / MAIN_REPORT
    if not main_path.exists():
        raise SystemExit(f"{main_path} is missing: run python -m undiscovered_research.backtest first.")
    main_report = json.loads(main_path.read_text(encoding="utf-8"))
    second = Path(args.second_sample)
    if not second.is_absolute():
        second = backtest.DATA.parent / second
    result = run(main_report, second.resolve())
    backtest.RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else backtest.RESULTS / "robustness.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
