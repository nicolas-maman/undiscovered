"""Checks run after the first test was published, outside its plan, and labelled so.

    python -m undiscovered_research.posthoc research-only

research-only: OpenAlex's random sample of a topic's works includes works
that are not research (datasets, editorials, errata, peer reviews...). The
first test sampled its abstracts that way. This reruns H1 exactly as the
robustness checks do (1,000 bootstrap draws), with each topic's sampled
abstracts limited to research types, the same rule the describing units use
(pipeline/distill_units.py, RESEARCH). The types are read from OpenAlex,
about 480 calls once, and kept in research/cache/types.json. The entry is
added to results/robustness.json with a label that says it is post hoc;
publish.py carries it to the site.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import requests

from . import backtest, embed, robustness
from .gentle import be_gentle

RESEARCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH_DIR.parent / "pipeline"))
import distill_units  # noqa: E402

TYPES = RESEARCH_DIR / "cache" / "types.json"


def work_types(ids: set[str]) -> dict[str, str]:
    """OpenAlex's type for each work, from the cache or fetched fifty at a time."""
    types = json.loads(TYPES.read_text(encoding="utf-8")) if TYPES.exists() else {}
    todo = sorted(ids - set(types))
    keyfile = RESEARCH_DIR / ".openalex_key"
    key = keyfile.read_text(encoding="utf-8").strip() if keyfile.exists() else ""
    for k in range(0, len(todo), 50):
        params = {"filter": "openalex:" + "|".join(todo[k:k + 50]), "per_page": 50, "select": "id,type"}
        if key:
            params["api_key"] = key
        resp = requests.get("https://api.openalex.org/works", params=params, timeout=90)
        resp.raise_for_status()
        for w in resp.json()["results"]:
            types[w["id"].rsplit("/", 1)[-1]] = w.get("type")
        time.sleep(0.15)
    TYPES.parent.mkdir(parents=True, exist_ok=True)
    TYPES.write_text(json.dumps(types), encoding="utf-8")
    return types


def research_only() -> dict:
    src = backtest.DATA
    dst = RESEARCH_DIR / "data_research_only"
    recs = {c: {f.name: json.loads(f.read_text(encoding="utf-8")) for f in (src / "topics" / c).glob("*.json")}
            for c in ("2011", "2017")}
    types = work_types({a["id"].rsplit("/", 1)[-1] for rs in recs.values() for r in rs.values() for a in r["abstracts"]})
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "topics").mkdir(parents=True)
    for name in ("sample.json", "sample_meta.json", "all_topics.json"):
        if (src / name).exists():
            shutil.copy(src / name, dst / name)
    dropped = 0
    for c, rs in recs.items():
        (dst / "topics" / c).mkdir()
        for name, rec in rs.items():
            keep = [a for a in rec["abstracts"] if types.get(a["id"].rsplit("/", 1)[-1]) in distill_units.RESEARCH]
            dropped += len(rec["abstracts"]) - len(keep)
            (dst / "topics" / c / name).write_text(json.dumps({**rec, "abstracts": keep}), encoding="utf-8")
    try:
        robustness._use_data(dst)
        report = backtest.run(1, 3, embed.TFIDF, n_boot=backtest.BOOTSTRAP_ROBUSTNESS)
    finally:
        robustness._use_data(src)
        shutil.rmtree(dst)
    return {"key": "research_only", "label": "After publication, not in the plan: research works only in the "
            "abstract samples", "abstracts_dropped": dropped, **robustness.summarise(report)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("check", choices=["research-only"])
    ap.parse_args()
    be_gentle()
    entry = research_only()
    path = backtest.RESULTS / "robustness.json"
    current = json.loads(path.read_text(encoding="utf-8"))
    current["variants"] = [v for v in current["variants"] if v["key"] != entry["key"]] + [entry]
    path.write_text(json.dumps(current, indent=1), encoding="utf-8")
    h1 = entry["hypotheses"]["H1_combined_beats_network"]
    print(f"{entry['abstracts_dropped']} abstracts dropped; H1 {h1['diff']:+.4f} {h1['diff_ci']} {h1['outcome']}")


if __name__ == "__main__":
    main()
