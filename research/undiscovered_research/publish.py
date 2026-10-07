"""Copy a finished backtest report into the site, with where it came from.

    python -m undiscovered_research.publish results/backtest_e1_k3_BAAI_bge-small-en-v1.5.json

writes ``data/backtest.json`` at the repository root, which the site's
results page reads. The file records the commit the report was produced
from, so every number on the site can be traced to code and to the plan in
``research/PREREGISTRATION.md`` as it stood at that commit.
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
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if _git("status", "--porcelain", "--", "research/undiscovered_research"):
        raise SystemExit("The analysis code has uncommitted changes; commit them first, "
                         "so the published numbers point at code that exists.")
    commit = _git("rev-parse", "HEAD")
    published = {
        "status": "complete",
        "published": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "commit": commit,
        "code": f"{GITHUB}/tree/{commit}/research",
        "preregistration": f"{GITHUB}/blob/{commit}/research/PREREGISTRATION.md",
        "report": report,
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(published, indent=1), encoding="utf-8")
    print(f"wrote {SITE_DATA.relative_to(REPO)} from commit {commit[:7]}")


if __name__ == "__main__":
    main()
