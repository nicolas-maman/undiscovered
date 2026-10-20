"""The ``undiscovered`` command.

    undiscovered setup          answer three questions once
    undiscovered work           take an open unit, do it, submit it
    undiscovered work --units 5 do five, one after another
    undiscovered work --dry-run do one and save it here instead of submitting
    undiscovered work --unit u-000241 --dry-run   a given unit, for example to compare clients
    undiscovered work --kind map                  map units even when a model is set up

With a model set up, ``work`` takes describing (distill) units, the job that
needs one; without one, map units.
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

from . import CLIENT, PROTOCOL, REPO, __version__, config, github, models
from . import distill
from .distill import PROMPT, Unusable, distill_unit
from .gentle import be_gentle
from .mapper import map_unit
from .openalex import BudgetExhausted, OpenAlex

UNITS_URL = f"https://raw.githubusercontent.com/{REPO}/map-2025/units/index.json"
DISTILL_URL = f"https://raw.githubusercontent.com/{REPO}/distill-2025/units/index.json"


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
    print("\n3. AI model, for describing papers. Map units need none; skip this to do those.")
    choose_model(cfg)
    print("\nSaved", config.save(cfg))


def choose_model(cfg: dict) -> None:
    """Offer the models on this machine, the services the client knows, or any other server."""
    options = [(f"{mid} ({server}, on this machine, free)", "openai-compatible", base, mid, "", "")
               for server, base, mid in models.local_models()]
    options += [(f"{name}: {cost}", kind, base, "", where, name) for name, kind, base, where, cost in models.PRESETS]
    options.append(("another server that speaks the OpenAI API", "openai-compatible", "", "", "", ""))
    print("   Which model? Any of these works; docs/MODELS.md compares them.")
    for i, (label, *_rest) in enumerate(options, 1):
        print(f"   {i:>2}. {label}")
    pick = input("   Number, or Enter to skip: ").strip()
    if not pick.isdigit() or not 1 <= int(pick) <= len(options):
        return
    _label, kind, base, mid, where, name = options[int(pick) - 1]
    if mid:                                     # a model already on this machine
        cfg["model"] = {"provider": kind, "base_url": base, "id": mid}
        return
    if not base and kind == "openai-compatible":
        base = input("   Its base URL, ending in /v1 for most servers: ").strip()
    mid = input(f"   Model name, exactly as {name or 'the server'} lists it: ").strip()
    if not mid:
        print("   No model name; nothing saved.")
        return
    hint = f" ({where})" if where else ""
    secret = getpass.getpass(f"   Key{hint}, or Enter if it needs none (input is hidden): ").strip()
    cfg["model"] = {"provider": kind, "base_url": base, "id": mid, **({"key": secret} if secret else {})}


def pick_unit(index: dict, done: set[str], rng: random.Random, model: str = "") -> dict | None:
    """A unit this volunteer has not done, and that the volunteer's model has not described.

    Units that already have another model's descriptions come first: a unit is
    complete, and its papers can be paired, once two different models have
    described it. Among those, and then among open units, the choice is random,
    so volunteers rarely collide.
    """
    todo = [u for u in index.get("units", []) if u.get("status") in ("open", "check")
            and u["unit"] not in done and model not in u.get("models", [])]
    waiting = [u for u in todo if u.get("status") == "check"]
    pool = waiting or todo
    return rng.choice(pool) if pool else None


def result_body(unit: dict, gist: str, sha: str) -> str:
    result = {"unit": unit["unit"], "protocol": PROTOCOL, "client": CLIENT, "gist": gist, "sha256": sha}
    return ("A map result from the undiscovered client. The checking job reads the JSON below.\n\n"
            "```json\n" + json.dumps(result, indent=1) + "\n```\n")


def describe_body(unit: dict, model: dict, descriptions: list[dict]) -> str:
    result = {"unit": unit["unit"], "protocol": PROTOCOL, "client": CLIENT, "model": model,
              "prompt": PROMPT, "descriptions": descriptions}
    return ("Descriptions from the undiscovered client. The checking job reads the JSON below.\n\n"
            "```json\n" + json.dumps(result, indent=1, ensure_ascii=False) + "\n```\n")


def do_distill(unit: dict, key: str, model: models.Model) -> list[dict]:
    """Describe one unit's works. The OpenAlex cache is deleted afterwards."""
    def progress(done: int, total: int) -> None:
        print(f"  {unit['unit']}: {done}/{total} papers", end="\r" if done < total else "\n", flush=True)
    with tempfile.TemporaryDirectory(prefix="undiscovered-") as tmp:
        return distill_unit(OpenAlex(Path(tmp), key), model, unit, progress)


def do_unit(unit: dict, key: str) -> str:
    """Map one unit and return the records as one JSON text. The cache is deleted afterwards."""
    with tempfile.TemporaryDirectory(prefix="undiscovered-") as tmp:
        records = map_unit(OpenAlex(Path(tmp), key), unit)
    return json.dumps({"unit": unit["unit"], "freeze": unit["freeze"], "records": records},
                      sort_keys=True, separators=(",", ":"))


def cmd_work(args) -> None:
    be_gentle()
    cfg = config.load()
    model = models.from_settings(cfg) if args.kind != "map" else None
    if args.kind == "distill" and model is None:
        sys.exit("Describing papers needs an AI model. Run: undiscovered setup")
    tok = None if args.dry_run else github.token()
    index = requests.get(DISTILL_URL if model else UNITS_URL, timeout=60).json()
    done = set(cfg.get("done", []))
    rng = random.Random()
    for n in range(1 if args.unit else args.units):     # a named unit is done once
        if args.unit:
            unit = next((u for u in index.get("units", []) if u["unit"] == args.unit), None)
            if unit is None:
                sys.exit(f"There is no unit {args.unit}.")
        else:
            unit = pick_unit(index, done, rng, distill.model_name(model.provenance) if model else "")
        if unit is None:
            print("No open units left for you. Thank you.")
            return
        if model:
            print(f"unit {unit['unit']}: {len(unit['works'])} papers to describe with {model.id}")
            try:
                descriptions = do_distill(unit, config.openalex_key(cfg), model)
            except BudgetExhausted as e:
                print(f"Stopped: {e}. Run the same command tomorrow.")
                return
            except Unusable as e:
                for wid, why in e.failed:
                    print(f"  {wid}: {why}")
                if e.described:
                    out = Path(f"undiscovered-{unit['unit']}-partial.md")
                    out.write_text(describe_body(unit, model.provenance, e.described), encoding="utf-8")
                    print(f"saved what the model did describe in {out}; it cannot be submitted as it is")
                sys.exit(f"Stopped: {e}. Nothing was submitted.")
            body = describe_body(unit, model.provenance, descriptions)
            if args.dry_run:
                out = Path(f"undiscovered-{unit['unit']}.md")
                out.write_text(body, encoding="utf-8")
                print(f"saved {out} ({len(descriptions)} descriptions), not submitted")
                return
            issue = github.open_issue(tok, REPO, f"distill result {unit['unit']}", body, [])
            done.add(unit["unit"])
            cfg["done"] = sorted(done)
            config.save(cfg)
            print(f"submitted: {issue}")
            continue
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
    w.add_argument("--kind", choices=["auto", "map", "distill"], default="auto",
                   help="map units, describing (distill) units, or auto: distill when a model is set up")
    w.set_defaults(func=cmd_work)
    args = ap.parse_args(argv)
    try:
        args.func(args)
    except (github.NoGitHubLogin, models.ModelError) as e:
        sys.exit(f"Stopped: {e}")
    except KeyboardInterrupt:
        sys.exit("Stopped. Nothing half-done was submitted.")


if __name__ == "__main__":
    main()
