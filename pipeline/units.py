"""Make the list of map units: every OpenAlex topic, ten to a unit.

    python pipeline/units.py --freeze 2025 --out <map branch>/units/index.json

The order is shuffled with a fixed seed, so units mix fields and the list
can be rebuilt exactly.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import requests

UNIT_SIZE = 10
SEED = 2025


def all_topic_ids() -> list[str]:
    ids, cursor = [], "*"
    while cursor:
        page = requests.get("https://api.openalex.org/topics", timeout=60,
                            params={"per_page": 200, "select": "id", "cursor": cursor}).json()
        ids += [t["id"].rsplit("/", 1)[-1] for t in page["results"]]
        cursor = page["meta"].get("next_cursor") if page["results"] else None
    return sorted(set(ids))


def make_units(topic_ids: list[str], freeze: int) -> dict:
    ids = sorted(topic_ids)
    random.Random(SEED).shuffle(ids)
    units = [{"unit": f"u-{i + 1:06d}", "kind": "map", "topics": ids[k:k + UNIT_SIZE],
              "freeze": freeze, "quorum": 1, "status": "open"}
             for i, k in enumerate(range(0, len(ids), UNIT_SIZE))]
    return {"freeze": freeze, "topics": len(ids), "units": units}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--freeze", type=int, default=2025)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    index = make_units(all_topic_ids(), args.freeze)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"{index['topics']} topics in {len(index['units'])} units -> {out}")


if __name__ == "__main__":
    main()
