"""The ``undiscovered`` command.

    undiscovered setup          answer three questions once
    undiscovered work           take an open unit, do it, submit it
    undiscovered work --units 5 do five, one after another
    undiscovered work --dry-run do one and save it here instead of submitting
    undiscovered work --unit u-000241 --dry-run   a given unit, for example to compare clients
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

import requests

from . import CLIENT, PROTOCOL, REPO, __version__, config, github
from .gentle import be_gentle
from .mapper import map_unit
from .openalex import BudgetExhausted, OpenAlex

UNITS_URL = f"https://raw.githubusercontent.com/{REPO}/map-2025/units/index.json"


def cmd_setup(_args) -> None:
    cfg = config.load()
    print("undiscovered setup. Everything you enter stays in", config.path())
    print("\n1. OpenAlex key (optional). Without one you get about 1,000 calls a day; a free key")
    print("   from https://openalex.org/settings/api gives about 10,000.")
    key = getpass.getpass("   Paste it, or press Enter to skip (input is hidden): ").strip()
    if key:
        cfg["openalex_key"] = key
    print("\n2. GitHub. Results are submitted from your own GitHub account.")
    try:
        github.token()
        print("   Found your GitHub login.")
    except github.NoGitHubLogin as e:
        print("  ", e)
    print("\n3. AI model: not needed for map units, which are the only kind open now.")
    print("\nSaved", config.save(cfg))


def pick_unit(index: dict, done: set[str], rng: random.Random) -> dict | None:
    """A random open unit this volunteer has not done. Random, so volunteers rarely collide."""
    todo = [u for u in index.get("units", []) if u.get("status") in ("open", "check")
            and u["unit"] not in done]
    return rng.choice(todo) if todo else None


def result_body(unit: dict, gist: str, sha: str) -> str:
    result = {"unit": unit["unit"], "protocol": PROTOCOL, "client": CLIENT, "gist": gist, "sha256": sha}
    return ("A map result from the undiscovered client. The checking job reads the JSON below.\n\n"
            "```json\n" + json.dumps(result, indent=1) + "\n```\n")


def do_unit(unit: dict, key: str) -> str:
    """Map one unit and return the records as one JSON text. The cache is deleted afterwards."""
    with tempfile.TemporaryDirectory(prefix="undiscovered-") as tmp:
        records = map_unit(OpenAlex(Path(tmp), key), unit)
    return json.dumps({"unit": unit["unit"], "freeze": unit["freeze"], "records": records},
                      sort_keys=True, separators=(",", ":"))


def cmd_work(args) -> None:
    be_gentle()
    cfg = config.load()
    tok = None if args.dry_run else github.token()
    index = requests.get(UNITS_URL, timeout=60).json()
    done = set(cfg.get("done", []))
    rng = random.Random()
    for n in range(args.units):
        if args.unit:
            unit = next((u for u in index.get("units", []) if u["unit"] == args.unit), None)
            if unit is None:
                sys.exit(f"There is no unit {args.unit}.")
        else:
            unit = pick_unit(index, done, rng)
        if unit is None:
            print("No open units left for you. Thank you.")
            return
        print(f"unit {unit['unit']}: {len(unit['topics'])} topics at the end of {unit['freeze']}")
        try:
            content = do_unit(unit, config.openalex_key(cfg))
        except BudgetExhausted as e:
            print(f"Stopped: {e}. Run the same command tomorrow.")
            return
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if args.dry_run:
            out = Path(f"undiscovered-{unit['unit']}.json")
            out.write_text(content, encoding="utf-8")
            print(f"saved {out} (sha256 {sha[:12]}), not submitted")
            return
        gist = github.create_gist(tok, f"{unit['unit']}.json", content,
                                  f"undiscovered map result {unit['unit']}")
        issue = github.open_issue(tok, REPO, f"map result {unit['unit']}", result_body(unit, gist, sha), [])
        done.add(unit["unit"])
        cfg["done"] = sorted(done)
        config.save(cfg)
        print(f"submitted: {issue}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="undiscovered", description="Lend your computer to undiscovered.")
    ap.add_argument("--version", action="version", version=f"undiscovered {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="answer three questions once").set_defaults(func=cmd_setup)
    w = sub.add_parser("work", help="take an open unit, do it, submit it")
    w.add_argument("--units", type=int, default=1, help="how many units to do (default 1)")
    w.add_argument("--dry-run", action="store_true", help="save the result here instead of submitting")
    w.add_argument("--unit", default="", help="do this unit rather than a random open one")
    w.set_defaults(func=cmd_work)
    args = ap.parse_args(argv)
    try:
        args.func(args)
    except github.NoGitHubLogin as e:
        sys.exit(str(e))
    except KeyboardInterrupt:
        sys.exit("Stopped. Nothing half-done was submitted.")


if __name__ == "__main__":
    main()
