"""Import describing results a maintainer made without GitHub issues, through the same checks.

    python pipeline/import_results.py <distill-2025 checkout> --by <github login> --batch <name> \\
        --note "<how the results were made>" RESULT...

Each RESULT is a result as a client writes it: the body of a result issue
(`undiscovered work --dry-run` saves one) or its JSON alone. Every one goes
through the checking job's own intake_distill, exactly as an issue would:
accepted results are stored under the name import-<batch>-<n>, rejected ones
are kept with their reason in rejected/. The import itself is recorded in
imports/<batch>.json: who ran it, when, how the results were made, and what
became of each. Nothing is committed: look at the branch's diff, run
pipeline/combine.py, maps.py and cites.py as the intake job does, and commit.

Issues are how volunteers send results, because they carry the sender's
identity and a public reply. A maintainer's own batch has both already, in
the commit and this record, and does not need hundreds of issues.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intake  # noqa: E402


def body_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text if "```json" in text else "```json\n" + text.strip() + "\n```\n"


def run(branch: Path, by: str, batch: str, note: str, paths: list[Path]) -> dict:
    record = {"batch": batch, "by": by, "note": note,
              "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "results": []}
    for n, path in enumerate(paths, 1):
        ref, body = f"import-{batch}-{n:03d}", body_of(path)
        try:
            unit = intake.json_block(body).get("unit")
            model = intake.json_block(body).get("model")
        except intake.Reject:
            unit, model = None, None
        try:
            reply, accepted = intake.intake_distill(branch, body, by, ref), True
        except intake.Reject as e:
            reply, accepted = f"Not accepted: {e}.", False
            intake.log_rejection(branch, {"number": ref, "user": {"login": by},
                                          "title": f"distill result {unit}", "body": body}, str(e))
        record["results"].append({"id": ref, "file": path.name, "unit": unit, "model": model,
                                  "accepted": accepted, "reply": reply})
    folder = branch / "imports"
    folder.mkdir(exist_ok=True)
    (folder / f"{batch}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"batch": batch, "results": len(paths), "accepted": sum(r["accepted"] for r in record["results"])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("branch", type=Path)
    ap.add_argument("--by", required=True, help="the maintainer's GitHub login")
    ap.add_argument("--batch", required=True, help="a short name for this import, such as 2026-10-19-local")
    ap.add_argument("--note", required=True, help="how the results were made: models, machine, client")
    ap.add_argument("results", type=Path, nargs="+")
    args = ap.parse_args()
    if (args.branch / "imports" / f"{args.batch}.json").exists():
        sys.exit(f"there is already an import named {args.batch}")
    print(json.dumps(run(args.branch, args.by, args.batch, args.note, args.results)))


if __name__ == "__main__":
    main()
