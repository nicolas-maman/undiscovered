"""Titles and abstracts of every paper in the describing set, for the site's map and search.

    python pipeline/abstracts.py <distill-2025 checkout>

Reads papers.json and known-twins.json and writes abstracts.jsonl, one paper
per line: {"work", "title", "year", "abstract"}, from OpenAlex (CC0), fifty
papers per request. Run once when a set is made; papers whose abstract
OpenAlex no longer has keep an empty one. Volunteers' clients still fetch
their units' abstracts themselves: this file is what the site reads.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "clients" / "python"))
from undiscovered.openalex import abstract_text  # noqa: E402

API = "https://api.openalex.org/works"
PER_CALL = 50


def works(branch: Path) -> list[str]:
    papers = json.loads((branch / "papers.json").read_text(encoding="utf-8"))
    twins = branch / "known-twins.json"
    extra = [p["work"] for p in json.loads(twins.read_text(encoding="utf-8"))["papers"]] if twins.exists() else []
    return sorted(set(papers) | set(extra))


def fetch(ids: list[str], session: requests.Session) -> dict[str, dict]:
    for attempt in range(6):
        resp = session.get(API, timeout=60, params={
            "filter": "openalex:" + "|".join(ids), "per_page": len(ids),
            "select": "id,title,publication_year,abstract_inverted_index"})
        if resp.status_code == 200:
            return {w["id"].rsplit("/", 1)[-1]: {"title": (w.get("title") or "").strip(),
                                                 "year": w.get("publication_year"),
                                                 "abstract": abstract_text(w.get("abstract_inverted_index"))}
                    for w in resp.json().get("results", [])}
        time.sleep(2 ** attempt)
    resp.raise_for_status()
    raise RuntimeError(f"OpenAlex answered {resp.status_code}")


def main() -> None:
    branch = Path(sys.argv[1])
    ids = works(branch)
    session = requests.Session()
    session.headers["User-Agent"] = "undiscovered-pipeline (https://github.com/nicolas-maman/undiscovered)"
    found: dict[str, dict] = {}
    for i in range(0, len(ids), PER_CALL):
        found.update(fetch(ids[i:i + PER_CALL], session))
        time.sleep(0.2)
    with (branch / "abstracts.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for w in ids:
            row = found.get(w, {"title": "", "year": None, "abstract": ""})
            f.write(json.dumps({"work": w, **row}, ensure_ascii=False) + "\n")
    print(f"{len(ids)} papers, {sum(1 for w in ids if found.get(w, {}).get('abstract'))} with an abstract")


if __name__ == "__main__":
    main()
