"""Check one submitted result and, if it is sound, store it.

Run by the intake workflow when an issue titled "map result u-..." or
"distill result u-..." is opened. Client authors can run the same checks on a
saved result first:

    python pipeline/intake.py --check undiscovered-u-000241.json u-000241
    python pipeline/intake.py --check undiscovered-u-100001.md u-100001

Distill results are described at the end of this file.

It reads only the JSON block in the issue, never runs anything from it,
fetches the gist the result names, checks its checksum and every record,
and writes to a checkout of the map branch:

    units/index.json          the units and their status
    records/<topic>.json      one accepted record per topic
    results/<unit>.json       who submitted what, for every accepted result

One unit in twenty also needs a second volunteer's result, which must
agree with the first. Prints the reply for the issue on the last line of
its output, as JSON.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import requests
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = Draft202012Validator(json.loads((ROOT / "schemas" / "map-record.schema.json").read_text(encoding="utf-8")))
RESULT = Draft202012Validator(json.loads((ROOT / "schemas" / "result.schema.json").read_text(encoding="utf-8")))

MAX_BYTES = 5_000_000
CHECK_EVERY = 20
GIST = re.compile(r"^https://gist\.github\.com/[A-Za-z0-9-]+/([0-9a-f]{20,40})$")
TOPIC = re.compile(r"^T[0-9]+$")
WORK = re.compile(r"^W[0-9]+$")
FORMAT = 1


class Reject(Exception):
    """The result cannot be accepted; the message says why, for the issue reply."""


def json_block(body: str) -> dict:
    m = re.search(r"```json\s*\n(.*?)\n```", body or "", flags=re.S)
    if not m:
        raise Reject("no JSON block found in the issue")
    try:
        result = json.loads(m.group(1))
    except ValueError as e:
        raise Reject(f"the JSON block does not parse: {e}") from e
    if not isinstance(result, dict):
        raise Reject("the JSON block is not an object")
    return result


def parse_result(body: str) -> dict:
    result = json_block(body)
    if not GIST.match(str(result.get("gist", ""))):
        raise Reject("the result does not name a gist at https://gist.github.com/<user>/<id>")
    if not re.fullmatch(r"[0-9a-f]{64}", str(result.get("sha256", ""))):
        raise Reject("the result has no valid sha256")
    if not re.fullmatch(r"u-[0-9]{6}", str(result.get("unit", ""))):
        raise Reject("the result names no valid unit")
    return result


def fetch_gist(url: str, token: str = "") -> str:
    gist_id = GIST.match(url).group(1)
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=60)
    if resp.status_code != 200:
        raise Reject(f"the gist could not be read (HTTP {resp.status_code})")
    files = list(resp.json().get("files", {}).values())
    if len(files) != 1:
        raise Reject("the gist must hold exactly one file")
    f = files[0]
    if f.get("size", 0) > MAX_BYTES:
        raise Reject("the gist's file is too large")
    if f.get("truncated"):
        raw = requests.get(f["raw_url"], timeout=120)
        if raw.status_code != 200:
            raise Reject("the gist's file could not be read")
        return raw.text
    return f.get("content", "")


def check_records(content: str, sha256: str, unit: dict) -> list[dict]:
    """The unit's records, or Reject with the first problem found."""
    if hashlib.sha256(content.encode("utf-8")).hexdigest() != sha256:
        raise Reject("the gist's content does not match the checksum in the issue")
    try:
        data = json.loads(content)
    except ValueError as e:
        raise Reject(f"the gist's content does not parse: {e}") from e
    if data.get("unit") != unit["unit"] or data.get("freeze") != unit["freeze"]:
        raise Reject("the gist is for another unit or freeze year")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("topic") for r in records if isinstance(r, dict)] != unit["topics"]:
        raise Reject("the records do not cover exactly the unit's topics, in order")
    f = unit["freeze"]
    for r in records:
        t = r["topic"]
        problem = next(iter(SCHEMA.iter_errors(r)), None)
        if problem is not None:
            where = "/".join(str(x) for x in problem.absolute_path) or "record"
            raise Reject(f"{t}: {where}: {problem.message[:200]}")
        if r.get("format") != FORMAT or r.get("freeze") != f:
            raise Reject(f"{t}: wrong format or freeze year")
        if r.get("train_window") != [f - 7, f] or r.get("recent_window") != [f - 2, f]:
            raise Reject(f"{t}: wrong windows")
        inst = r.get("instrument")
        if not isinstance(inst, list) or len(inst) > 100 or not all(isinstance(w, str) and WORK.match(w) for w in inst):
            raise Reject(f"{t}: reference papers are not a list of at most 100 work IDs")
        if not isinstance(r.get("usable_abstracts"), int) or not 0 <= r["usable_abstracts"] <= 40:
            raise Reject(f"{t}: usable_abstracts must be a whole number from 0 to 40")
        by_year = r.get("works_by_year")
        if not isinstance(by_year, dict) or not all(
                str(y).isdigit() and f - 7 <= int(y) <= f and isinstance(n, int) and n >= 0
                for y, n in by_year.items()):
            raise Reject(f"{t}: works_by_year is not a count per year of the train window")
        if r.get("size") != sum(by_year.values()):
            raise Reject(f"{t}: size is not the sum of works_by_year")
        for window in ("cited_by_train", "cited_by_recent", "cited_by_before"):
            counts = r.get(window)
            if not isinstance(counts, dict) or not all(
                    TOPIC.match(k) and isinstance(v, int) and v >= 0 for k, v in counts.items()):
                raise Reject(f"{t}: {window} is not a count per topic")
    return records


def needs_check(unit_id: str) -> bool:
    """One unit in twenty, chosen by its name, gets a second volunteer."""
    return int(hashlib.sha256(unit_id.encode()).hexdigest(), 16) % CHECK_EVERY == 0


def agree(first: list[dict], second: list[dict]) -> tuple[bool, str]:
    """Two volunteers' records for a unit agree within the drift of a live index."""
    for a, b in zip(first, second):
        ia, ib = set(a["instrument"]), set(b["instrument"])
        overlap = len(ia & ib) / max(len(ia | ib), 1)
        ta, tb = sum(a["cited_by_train"].values()), sum(b["cited_by_train"].values())
        if overlap < 0.9 or abs(ta - tb) > max(5, 0.05 * max(ta, tb)):
            return False, f"{a['topic']}: reference papers overlap {overlap:.0%}, citing works {ta} against {tb}"
    return True, "the two results agree"


def intake(map_dir: Path, body: str, author: str, issue: int, token: str = "",
           fetch=fetch_gist) -> str:
    """Process one issue against a checkout of the map branch. Returns the reply."""
    index_path = map_dir / "units" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    result = parse_result(body)
    unit = next((u for u in index["units"] if u["unit"] == result["unit"]), None)
    if unit is None:
        raise Reject(f"there is no unit {result['unit']}")
    if unit["status"] in ("done", "disputed"):
        return f"Unit {unit['unit']} is already complete. Thank you all the same."
    records = check_records(fetch(result["gist"], token), result["sha256"], unit)
    provenance = {"issue": issue, "author": author, "gist": result["gist"], "sha256": result["sha256"],
                  "client": result.get("client")}
    res_path = map_dir / "results" / f"{unit['unit']}.json"
    results = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else []
    if unit["status"] == "open":
        for r in records:
            p = map_dir / "records" / f"{r['topic']}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(r, sort_keys=True), encoding="utf-8")
        unit["status"] = "check" if needs_check(unit["unit"]) else "done"
        reply = (f"Accepted: {len(records)} topic records for {unit['unit']}. " +
                 ("This unit will also be done by a second volunteer, as one in twenty are."
                  if unit["status"] == "check" else "Thank you."))
    else:   # "check": a second result from someone else
        if any(r["author"] == author for r in results):
            raise Reject("a second result for a checked unit must come from another volunteer")
        first = [json.loads((map_dir / "records" / f"{t}.json").read_text(encoding="utf-8"))
                 for t in unit["topics"]]
        ok, detail = agree(first, records)
        unit["status"] = "done" if ok else "disputed"
        reply = (f"Second result for {unit['unit']}: {detail}. " +
                 ("The unit is complete. Thank you." if ok else "The unit is set aside for a look."))
    results.append(provenance)
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    return reply


# Distill results. The descriptions travel in the issue itself (twenty fit
# easily), so there is no gist. Each is checked with the client's own
# functions, so a result that passed the client's checks passes these:
# both parts present and short, and at most the unit's max_avoided of the
# paper's distinctive words reused. A unit needs results from `quorum`
# different volunteers; each result is kept whole under
# results/<unit>/<issue>.json on the distill branch, with its model.
# Agreement between models and known twins, the protocol's other two
# checks, are applied when results are combined, not here.

MIN_COVERED = 0.75          # a result describes at least this share of the unit's papers


def check_descriptions(result: dict, unit: dict) -> list[dict]:
    """The result's descriptions, or Reject with the first problem found."""
    from undiscovered import distill
    if "descriptions" in result and result.get("prompt") != distill.PROMPT:
        raise Reject(f"the result was made with prompt {result.get('prompt')}; this unit needs prompt "
                     f"{distill.PROMPT}, so update the client")
    problem = next(iter(RESULT.iter_errors(result)), None)
    if problem is not None or "descriptions" not in result:
        where = "/".join(str(x) for x in problem.absolute_path) if problem else "descriptions"
        raise Reject(f"{where or 'result'}: {problem.message[:200] if problem else 'missing'}")
    if result.get("unit") != unit["unit"]:
        raise Reject("the result is for another unit")
    descs, seen = result["descriptions"], set()
    for d in descs:
        w = d["work"]
        if w not in unit["works"] or w in seen:
            raise Reject(f"{w} is not one of the unit's papers, or is described twice")
        seen.add(w)
        try:
            distill.check({"problem": " ".join(d["problem"].split()), "approach": " ".join(d["approach"].split())},
                          unit.get("avoid", {}).get(w, []), unit.get("max_avoided", 2))
        except distill.Unusable as e:
            raise Reject(f"{w}: {e}") from None
    if len(seen) < MIN_COVERED * len(unit["works"]):
        raise Reject(f"only {len(seen)} of the unit's {len(unit['works'])} papers are described")
    return descs


def intake_distill(dist_dir: Path, body: str, author: str, issue: int) -> str:
    """Process one distill result against a checkout of the distill branch. Returns the reply."""
    index_path = dist_dir / "units" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    result = json_block(body)
    unit = next((u for u in index["units"] if u["unit"] == result.get("unit")), None)
    if unit is None:
        raise Reject(f"there is no describing unit {result.get('unit')}")
    if unit["status"] == "done":
        return f"Unit {unit['unit']} already has all the results it needs. Thank you all the same."
    descs = check_descriptions(result, unit)
    folder = dist_dir / "results" / unit["unit"]
    earlier = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
    if any(r["author"] == author for r in earlier):
        raise Reject("each volunteer describes a unit once; its second result must come from someone else")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{issue}.json").write_text(json.dumps(
        {"issue": issue, "author": author, "client": result.get("client"), "model": result["model"],
         "prompt": result["prompt"], "descriptions": descs}, indent=1, ensure_ascii=False), encoding="utf-8")
    have = len(earlier) + 1
    unit["status"] = "done" if have >= unit.get("quorum", 2) else "check"
    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    model = f"{result['model']['id']} ({result['model']['provider']})"
    return (f"Accepted: {len(descs)} descriptions for {unit['unit']}, made with {model}. " +
            ("The unit is complete. Thank you." if unit["status"] == "done"
             else f"It needs {unit.get('quorum', 2) - have} more from another volunteer. Thank you."))


UNITS_URL = "https://raw.githubusercontent.com/nicolas-maman/undiscovered/map-2025/units/index.json"
DISTILL_URL = "https://raw.githubusercontent.com/nicolas-maman/undiscovered/distill-2025/units/index.json"


def check_file(path: str, unit_id: str) -> int:
    """For client authors: run the intake checks on a saved result, before submitting it."""
    content = Path(path).read_text(encoding="utf-8")
    distill_result = path.endswith(".md")
    index = requests.get(DISTILL_URL if distill_result else UNITS_URL, timeout=60).json()
    unit = next((u for u in index["units"] if u["unit"] == unit_id), None)
    if unit is None:
        print(f"there is no unit {unit_id}")
        return 1
    try:
        if distill_result:
            found = f"{len(check_descriptions(json_block(content), unit))} descriptions"
        else:
            found = f"{len(check_records(content, hashlib.sha256(content.encode('utf-8')).hexdigest(), unit))} records"
    except Reject as e:
        print(f"would be rejected: {e}")
        return 1
    print(f"would be accepted: {found} for {unit_id}")
    return 0


def main() -> int | None:
    if len(sys.argv) == 4 and sys.argv[1] == "--check":
        return check_file(sys.argv[2], sys.argv[3])
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event["issue"]
    body, author, number = issue.get("body") or "", issue["user"]["login"], issue["number"]
    try:
        if issue.get("title", "").startswith("distill result"):
            reply = intake_distill(Path(os.environ["DISTILL_DIR"]), body, author, number)
        else:
            reply = intake(Path(os.environ["MAP_DIR"]), body, author, number, os.environ.get("GITHUB_TOKEN", ""))
        ok = True
    except Reject as e:
        reply, ok = f"Not accepted: {e}.", False
    print(json.dumps({"accepted": ok, "reply": reply}))


if __name__ == "__main__":
    sys.exit(main())
