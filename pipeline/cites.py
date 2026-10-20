"""Mark each published pair with whether its two papers already cite each other.

    python pipeline/cites.py <distill-2025 checkout>

Reads combined/twins.json, asks OpenAlex for the reference lists of every
paper in a pair (fifty papers a request), and writes back, for each pair,
"cites": "a cites b", "b cites a", "both" or "neither". A pair whose papers
already cite each other is a connection that has been made; one where
neither does is a lead. A paper's citations of the other's field are not
checked here: that is the map records' job.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

API = "https://api.openalex.org/works"
PER_CALL = 50


def references(works: list[str], session: requests.Session) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for i in range(0, len(works), PER_CALL):
        ids = works[i:i + PER_CALL]
        for attempt in range(6):
            resp = session.get(API, timeout=60, params={"filter": "openalex:" + "|".join(ids),
                                                         "per_page": len(ids), "select": "id,referenced_works"})
            if resp.status_code == 200:
                break
            time.sleep(2 ** attempt)
        resp.raise_for_status()
        for w in resp.json().get("results", []):
            out[w["id"].rsplit("/", 1)[-1]] = {r.rsplit("/", 1)[-1] for r in w.get("referenced_works") or []}
    return out


def verdict(a: str, b: str, refs: dict[str, set[str]]) -> str:
    ab, ba = b in refs.get(a, set()), a in refs.get(b, set())
    return "both" if ab and ba else "a cites b" if ab else "b cites a" if ba else "neither"


def mark(branch: Path, fetch=references) -> dict:
    path = branch / "combined" / "twins.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs = data.get("twins", []) + data.get("known_cases", [])
    works = sorted({w for t in pairs for w in (t["a"]["work"], t["b"]["work"])})
    if not works:
        return {"pairs": 0}
    session = requests.Session()
    session.headers["User-Agent"] = "undiscovered-pipeline (https://github.com/nicolas-maman/undiscovered)"
    refs = fetch(works, session)
    for t in pairs:
        t["cites"] = verdict(t["a"]["work"], t["b"]["work"], refs)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"pairs": len(pairs), "neither": sum(t["cites"] == "neither" for t in pairs)}


if __name__ == "__main__":
    print(json.dumps(mark(Path(sys.argv[1]))))
