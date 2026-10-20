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
    progress.json             counts for the site: units by status, contributors

One unit in twenty also needs a second volunteer's result, which must
agree with the first. Prints the reply for the issue on the last line of
its output, as JSON.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
from collections import Counter
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
    res_path = map_dir / "results" / f"{unit['unit']}.json"
    results = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else []
    if any(r["issue"] == issue for r in results):
        return f"This result for {unit['unit']} is already stored. Thank you."
    if unit["status"] in ("done", "disputed"):
        return f"Unit {unit['unit']} is already complete. Thank you all the same."
    records = check_records(fetch(result["gist"], token), result["sha256"], unit)
    provenance = {"issue": issue, "author": author, "gist": result["gist"], "sha256": result["sha256"],
                  "client": result.get("client")}
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
    write_progress(map_dir, map_progress(map_dir))
    return reply


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_progress(branch: Path, progress: dict) -> None:
    (branch / "progress.json").write_text(json.dumps(progress, indent=1, ensure_ascii=False), encoding="utf-8")


def map_progress(map_dir: Path) -> dict:
    """What the site shows about the map: units by status, topics recorded, who did them."""
    index = json.loads((map_dir / "units" / "index.json").read_text(encoding="utf-8"))
    units = Counter()
    for f in sorted((map_dir / "results").glob("*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            units[r["author"]] += 1
    return {"job": "map", "freeze": index.get("freeze"), "updated": _now(),
            "topics": index.get("topics"), "topics_recorded": len(list((map_dir / "records").glob("*.json"))),
            "units": dict(sorted(Counter(u["status"] for u in index["units"]).items())),
            "contributors": [{"login": a, "units": n} for a, n in sorted(units.items(), key=lambda x: (-x[1], x[0]))]}


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
    descs, seen, taken = result["descriptions"], set(), set()
    for d in descs:
        w = d["work"]
        if w not in unit["works"] or w in seen:
            raise Reject(f"{w} is not one of the unit's papers, or is described twice")
        seen.add(w)
        desc = {"problem": " ".join(d["problem"].split()), "approach": " ".join(d["approach"].split())}
        try:
            distill.check(desc, unit.get("avoid", {}).get(w, []), unit.get("max_avoided", 2), taken)
        except distill.Unusable as e:
            raise Reject(f"{w}: {e}") from None
        taken.add(distill.fingerprint(desc))
    if len(seen) < MIN_COVERED * len(unit["works"]):
        raise Reject(f"only {len(seen)} of the unit's {len(unit['works'])} papers are described")
    return descs


REJECTED_SHOWN = 500      # rejections listed in rejected/index.json, latest first, for the site
RELEVANT_TOP = 0.15       # a description should find its own paper's abstract in this top share of the unit's
RELEVANT_SHARE = 0.5      # share of a result's descriptions that must, where the abstracts are known


def relevance(descs: list[dict], abstracts: dict[str, str]) -> float | None:
    """Share of descriptions whose own paper's abstract is among the most like them in the unit.

    Each description is compared, by TF-IDF cosine, with the abstracts of the
    papers the result describes, and should find its own in the top
    RELEVANT_TOP of them (3 of a unit of 20). Descriptions written for the
    right papers find their own abstract first eight or nine times in ten,
    even without the field's words (two small models on five units, October
    2026); descriptions of the wrong papers, or of none, find it by chance,
    about three times in twenty. None when fewer than four abstracts are known.
    """
    known = [d for d in descs if abstracts.get(d["work"])]
    if len(known) < 4:
        return None
    from sklearn.feature_extraction.text import TfidfVectorizer
    texts = [abstracts[d["work"]] for d in known] + [f"{d['problem']} {d['approach']}" for d in known]
    M = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts)
    sims = (M[len(known):] @ M[:len(known)].T).toarray()
    top = max(1, round(RELEVANT_TOP * len(known)))
    hits = sum(int((sims[i] > sims[i, i]).sum()) < top for i in range(len(known)))
    return hits / len(known)


def unit_abstracts(dist_dir: Path, works: list[str]) -> dict[str, str]:
    """Title and abstract of each of a unit's papers, from the branch's abstracts.jsonl."""
    path, want, out = dist_dir / "abstracts.jsonl", set(works), {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["work"] in want and row.get("abstract"):
                out[row["work"]] = f"{row.get('title', '')} {row['abstract']}"
    return out


def intake_distill(dist_dir: Path, body: str, author: str, issue: int) -> str:
    """Process one distill result against a checkout of the distill branch. Returns the reply."""
    index_path = dist_dir / "units" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    result = json_block(body)
    unit = next((u for u in index["units"] if u["unit"] == result.get("unit")), None)
    if unit is None:
        raise Reject(f"there is no describing unit {result.get('unit')}")
    if (dist_dir / "results" / unit["unit"] / f"{issue}.json").exists():
        return f"This result for {unit['unit']} is already stored. Thank you."
    if unit["status"] == "done":
        return f"Unit {unit['unit']} already has all the results it needs. Thank you all the same."
    descs = check_descriptions(result, unit)
    match = relevance(descs, unit_abstracts(dist_dir, unit["works"]))
    if match is not None and match < RELEVANT_SHARE:
        raise Reject(f"only {round(match * 100)}% of the descriptions find their own paper's abstract among the "
                     "most like them in the unit; they may describe other papers, or nothing")
    folder = dist_dir / "results" / unit["unit"]
    earlier = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
    from undiscovered.distill import model_name
    model = model_name(result["model"])
    if any(model_name(r["model"]) == model for r in earlier):
        raise Reject(f"this unit already has descriptions made with {model}; it needs another model, "
                     "from anyone, so that two models can check each other")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{issue}.json").write_text(json.dumps(
        {"issue": issue, "author": author, "client": result.get("client"), "model": result["model"],
         "prompt": result["prompt"], "relevance": match, "at": _now(), "descriptions": descs},
        indent=1, ensure_ascii=False), encoding="utf-8")
    unit["models"] = sorted({model_name(r["model"]) for r in earlier} | {model})
    unit["results"] = sorted([{"issue": r["issue"], "author": r["author"], "model": model_name(r["model"]),
                               "relevance": r.get("relevance")} for r in earlier] +
                             [{"issue": issue, "author": author, "model": model, "relevance": match}],
                             key=lambda r: r["issue"])
    have = len(unit["models"])
    unit["status"] = "done" if have >= unit.get("quorum", 2) else "check"
    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    write_progress(dist_dir, distill_progress(dist_dir))
    return (f"Accepted: {len(descs)} descriptions for {unit['unit']}, made with {model}. " +
            ("The unit is complete. Thank you." if unit["status"] == "done"
             else f"It needs descriptions from {unit.get('quorum', 2) - have} more model(s), not {model}, "
                  "from anyone. Thank you."))


def log_rejection(store: Path, issue: dict, reason: str) -> None:
    """Keep every rejected result's reason on the data branch, so the site can show what goes wrong."""
    result = {}
    try:
        result = json_block(issue.get("body") or "")
    except Reject:
        pass
    folder = store / "rejected"
    folder.mkdir(exist_ok=True)
    (folder / f"{issue['number']}.json").write_text(json.dumps(
        {"issue": issue["number"], "author": issue["user"]["login"], "title": issue.get("title", ""),
         "unit": result.get("unit"), "client": result.get("client"), "model": result.get("model"),
         "reason": reason, "at": _now()}, indent=1, ensure_ascii=False), encoding="utf-8")
    log = sorted((json.loads(f.read_text(encoding="utf-8")) for f in folder.glob("[0-9]*.json")),
                 key=lambda r: -r["issue"])
    (folder / "index.json").write_text(json.dumps({"rejected": len(log), "latest": log[:REJECTED_SHOWN]},
                                                  indent=1, ensure_ascii=False), encoding="utf-8")


def distill_progress(dist_dir: Path) -> dict:
    """What the site shows about describing: units by status, descriptions, contributors and models."""
    index = json.loads((dist_dir / "units" / "index.json").read_text(encoding="utf-8"))
    people: dict[str, Counter] = {}
    models: dict[tuple[str, str], Counter] = {}
    described = set()
    for f in sorted((dist_dir / "results").glob("*/*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        n = len(r["descriptions"])
        described.update(d["work"] for d in r["descriptions"])
        people.setdefault(r["author"], Counter()).update(units=1, descriptions=n)
        models.setdefault((r["model"]["provider"], r["model"]["id"]), Counter()).update(units=1, descriptions=n)
    order = lambda item: (-item[1]["descriptions"], item[0])  # noqa: E731
    return {"job": "distill", "set": index.get("set"), "updated": _now(), "papers": index.get("papers"),
            "papers_described": len(described),
            "descriptions": sum(c["descriptions"] for c in people.values()),
            "units": dict(sorted(Counter(u["status"] for u in index["units"]).items())),
            "contributors": [{"login": a, **c} for a, c in sorted(people.items(), key=order)],
            "models": [{"provider": k[0], "id": k[1], **c} for k, c in sorted(models.items(), key=order)]}


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
    # INTAKE_EVENT lets CI rehearse with an issue of its own: Actions does not let
    # a step change GITHUB_EVENT_PATH.
    event = json.loads(Path(os.environ.get("INTAKE_EVENT") or os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event["issue"]
    body, author, number = issue.get("body") or "", issue["user"]["login"], issue["number"]
    distill_result = issue.get("title", "").startswith("distill result")
    store = Path(os.environ["DISTILL_DIR" if distill_result else "MAP_DIR"])
    try:
        if distill_result:
            reply = intake_distill(store, body, author, number)
        else:
            reply = intake(store, body, author, number, os.environ.get("GITHUB_TOKEN", ""))
        ok = True
    except Reject as e:
        reply, ok = f"Not accepted: {e}.", False
        log_rejection(store, issue, str(e))
    print(json.dumps({"accepted": ok, "reply": reply}))


if __name__ == "__main__":
    sys.exit(main())
