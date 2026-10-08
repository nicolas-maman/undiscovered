r"""Copy a finished backtest report into the site, with where it came from.

    python -m undiscovered_research.publish \
        results/backtest_e1_k3_tfidf.json --robustness results/robustness.json

writes ``data/backtest.json`` at the repository root, which the site's
results page reads. The report records the commit whose code produced it,
and publishing refuses a report made with uncommitted changes, so every
number on the site can be traced to code and to the plan in
``research/PREREGISTRATION.md`` as they stood at that commit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SITE_DATA = REPO / "data" / "backtest.json"
GITHUB = "https://github.com/nicolas-maman/undiscovered"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True,
                          text=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report", help="a results/*.json file written by backtest.py")
    ap.add_argument("--robustness", default="", help="results/robustness.json, if run")
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if report.get("decision") not in ("continue", "stop"):
        raise SystemExit("The report has no decision (the stricter-label check is missing); "
                         "run python -m undiscovered_research.backtest.")
    config = report.get("config", {})
    commit = config.get("commit", "")
    if not commit or config.get("code_changed", True):
        raise SystemExit("The report does not come from committed analysis code; commit the code, "
                         "run the analysis again, then publish.")
    try:
        _git("cat-file", "-e", f"{commit}^{{commit}}")
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Commit {commit[:7]} from the report is not in this repository.") from e
    robustness = None
    if args.robustness:
        robustness = json.loads(Path(args.robustness).read_text(encoding="utf-8"))["variants"]
        main_run = next((v for v in robustness if v.get("key") == "main"), {})
        if main_run.get("hypotheses") != report.get("hypotheses"):
            raise SystemExit("The robustness file's main run does not match the report; "
                             "rerun both from the same data and code.")
    published = {
        "status": "complete",
        "published": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        # The commit whose code produced the numbers, not the one checked out now.
        "commit": commit,
        "code": f"{GITHUB}/tree/{commit}/research",
        "preregistration": f"{GITHUB}/blob/{commit}/research/PREREGISTRATION.md",
        "report": report,
    }
    if robustness is not None:
        published["robustness"] = robustness
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False: a NaN would make the file invalid JSON for the page.
    SITE_DATA.write_text(json.dumps(published, indent=1, allow_nan=False), encoding="utf-8")
    print(f"wrote {SITE_DATA} for commit {commit[:7]}")


if __name__ == "__main__":
    main()
