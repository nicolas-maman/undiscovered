"""Every JSON example in PROTOCOL.md must pass the schemas it illustrates.

The examples are what client authors copy, so an example that breaks the
protocol's own rules is a bug in the protocol.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pytest
import requests
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
SCHEMAS = {p.stem.split(".")[0]: json.loads(p.read_text(encoding="utf-8"))
           for p in (REPO / "schemas").glob("*.schema.json")}


def examples() -> list[str]:
    text = (REPO / "PROTOCOL.md").read_text(encoding="utf-8")
    return re.findall(r"```json\n(.*?)```", text, flags=re.S)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_schemas_are_valid(name):
    Draft202012Validator.check_schema(SCHEMAS[name])


def test_every_protocol_example_validates():
    seen = set()
    for block in examples():
        block = block.strip()
        if block.startswith('"descriptions"'):
            # A fragment: the field that replaces "ranking" in a distill result.
            fragment = json.loads("{" + block + "}")
            item_schema = {**SCHEMAS["result"]["properties"]["descriptions"],
                           "$schema": SCHEMAS["result"]["$schema"]}
            Draft202012Validator(item_schema).validate(fragment["descriptions"])
            seen.add("descriptions")
            continue
        obj = json.loads(block)
        kind = "unit" if "kind" in obj else "result" if "client" in obj else \
            "rating" if "rating" in obj else None
        assert kind, f"example matches no schema: {block[:80]}"
        Draft202012Validator(SCHEMAS[kind]).validate(obj)
        seen.add(obj.get("kind", kind))
    assert {"map", "distill", "rank", "result", "rating", "descriptions"} <= seen


def test_bridge_ids_in_examples_are_sorted():
    text = (REPO / "PROTOCOL.md").read_text(encoding="utf-8")
    for a, b in re.findall(r"b-(T[0-9]+)-(T[0-9]+)", text):
        assert a < b, f"b-{a}-{b}: topic IDs must be in sorted order"


ONLINE = os.environ.get("UNDISCOVERED_ONLINE") == "1"


def _lookup(path: str) -> dict | None:
    """One OpenAlex record (single-record lookups cost nothing), or None if absent."""
    for attempt in range(3):
        try:
            resp = requests.get(f"https://api.openalex.org/{path}", timeout=30)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            return resp.json()
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"OpenAlex unreachable for {path}")


@pytest.mark.skipif(not ONLINE, reason="set UNDISCOVERED_ONLINE=1 to check IDs against OpenAlex")
def test_example_ids_exist_and_evidence_matches_topics():
    text = (REPO / "PROTOCOL.md").read_text(encoding="utf-8")
    for wid in sorted(set(re.findall(r"\bW[0-9]{6,}\b", text))):
        assert _lookup(f"works/{wid}?select=id"), f"{wid} does not exist in OpenAlex"
    for tid in sorted(set(re.findall(r"\bT[0-9]{5}\b", text))):
        assert _lookup(f"topics/{tid}?select=id"), f"{tid} does not exist in OpenAlex"

    blocks = [json.loads(b) for b in examples() if not b.strip().startswith('"')]
    units = {b["unit"]: b for b in blocks if "kind" in b}
    for result in (b for b in blocks if "client" in b and "evidence" in b):
        unit = units[result["unit"]]
        for ev in result["evidence"]:
            for wid, tid in zip(ev["works"], (unit["topic"], ev["candidate"])):
                work = _lookup(f"works/{wid}?select=topics")
                topics = {t["id"].rsplit("/", 1)[-1] for t in work.get("topics") or []}
                assert tid in topics, f"{wid} is not in topic {tid}"
