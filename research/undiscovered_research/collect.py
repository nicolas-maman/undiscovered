"""Collect everything the backtest needs from OpenAlex, per topic and cutoff.

For a cutoff year C (the literature is "frozen" at the end of C):

* train window = [C-7, C], test window = [C+1, C+6].
* Topics are OpenAlex *primary* topics throughout: a work counts once, under
  the topic it is most about, rather than under each of up to three topics.
* instrument  = the topic's 100 most-cited papers published up to C. A link
  from topic A to topic B in a window is the number of works whose primary
  topic is A, published in that window, that cite any of B's instrument
  papers. One request (``group_by=primary_topic.id``) returns that count for
  every citing topic at once.
* train window: the full distribution over all citing topics (cursor-paged),
  because the network features need each topic's whole neighbourhood.
* test window: only the citing topics in the sample, asked in chunks of 100
  (the OR limit). The labels only concern sampled pairs, and this costs
  ceil(n/100) requests instead of paging through every citing topic.
* abstracts   = a random sample (OpenAlex ``sample`` + ``seed``) of the
  topic's papers in the train window that have an abstract. Random rather
  than most-cited, because all-time citation counts include citations made
  after the cutoff: choosing by them would leak the future into the
  predictors.
* size        = the number of the topic's works in the train window.

Everything lands in ``research/data/topics/<cutoff>/<topic>.json``.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from . import openalex as oa

DATA = Path(__file__).resolve().parent.parent / "data"
CUTOFFS = (2011, 2017)          # 2011 fits the models; 2017 is the evaluation
TRAIN_YEARS = 7                 # train window [C-7, C]
TEST_YEARS = 6                  # test window  [C+1, C+6]
INSTRUMENT = 100                # papers per topic that define "citing the topic"
ABSTRACTS = 40                  # random abstracts per topic per cutoff
SAMPLE_SEED = 17


def all_topics() -> list[dict]:
    """Every OpenAlex topic with its place in the hierarchy."""
    out = []
    for page in oa.paged("topics", {"per_page": 200,
                                    "select": "id,display_name,subfield,field,domain,works_count"}):
        for t in page["results"]:
            out.append({
                "id": oa.short_id(t["id"]),
                "name": t["display_name"],
                "subfield": t["subfield"]["display_name"],
                "field": t["field"]["display_name"],
                "domain": t["domain"]["display_name"],
                "works_count": t["works_count"],
            })
    return out


def sample_topics(topics: list[dict], per_domain: int, seed: int) -> list[dict]:
    """The same number of topics from each domain, reproducibly."""
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for t in topics:
        by_domain[t["domain"]].append(t)
    rng = random.Random(seed)
    chosen = []
    for domain in sorted(by_domain):
        pool = sorted(by_domain[domain], key=lambda t: t["id"])
        chosen.extend(rng.sample(pool, min(per_domain, len(pool))))
    return chosen


def _citing_counts(instrument: list[str], start: int | None, end: int,
                   only: list[str] | None = None) -> dict[str, int]:
    """Works published in [start, end] citing any instrument paper, by primary topic.

    ``start=None`` means every year up to ``end``.

    With ``only``, restrict the citing works to those primary topics, asked
    100 at a time (OpenAlex's OR limit): one page per chunk, since a chunk
    can produce at most 100 groups.
    """
    counts: dict[str, int] = {}
    years = f"<{end + 1}" if start is None else f"{start}-{end}"
    base = f"referenced_works:{'|'.join(instrument)},publication_year:{years}"
    chunks = [None] if only is None else [only[i:i + 100] for i in range(0, len(only), 100)]
    for chunk in chunks:
        flt = base if chunk is None else f"{base},primary_topic.id:{'|'.join(chunk)}"
        for page in oa.paged("works", {"filter": flt, "group_by": "primary_topic.id",
                                       "per_page": 200}):
            for g in page.get("group_by", []):
                if g.get("key") and g["key"] != "unknown":
                    counts[oa.short_id(g["key"])] = int(g["count"])
    return counts


def collect_topic(topic_id: str, cutoff: int, sampled: list[str]) -> dict:
    train = (cutoff - TRAIN_YEARS, cutoff)
    test = (cutoff + 1, cutoff + TEST_YEARS)

    top = oa.get("works", {
        "filter": f"primary_topic.id:{topic_id},publication_year:<{cutoff + 1}",
        "sort": "cited_by_count:desc",
        "per_page": INSTRUMENT,
        "select": "id",
    })
    instrument = [oa.short_id(w["id"]) for w in top["results"]]

    size = oa.get("works", {
        "filter": f"primary_topic.id:{topic_id},publication_year:{train[0]}-{train[1]}",
        "per_page": 1, "select": "id",
    })["meta"]["count"]

    sample = oa.get("works", {
        "filter": f"primary_topic.id:{topic_id},publication_year:{train[0]}-{train[1]},has_abstract:true",
        "sample": ABSTRACTS, "seed": SAMPLE_SEED, "per_page": ABSTRACTS,
        "select": "id,title,abstract_inverted_index,publication_year",
    })
    abstracts = [{
        "id": oa.short_id(w["id"]),
        "year": w.get("publication_year"),
        "text": f"{w.get('title') or ''}. {oa.abstract_text(w.get('abstract_inverted_index'))}".strip(),
    } for w in sample["results"]]

    return {
        "topic": topic_id,
        "cutoff": cutoff,
        "train_window": train,
        "test_window": test,
        "size": size,
        "instrument": instrument,
        "abstracts": abstracts,
        "cited_by_train": _citing_counts(instrument, *train) if instrument else {},
        # Every year before the train window, for the sampled topics only: a
        # pair is "not yet connected" only if it was never linked before the
        # cutoff, as in Science4Cast, not merely quiet in the train window.
        "cited_by_before": (_citing_counts(instrument, None, train[0] - 1, only=sampled)
                            if instrument else {}),
        "cited_by_test": _citing_counts(instrument, *test, only=sampled) if instrument else {},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--per-domain", type=int, default=75)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--data", default="", help="data directory (default research/data); "
                    "use a separate one for each topic sample")
    args = ap.parse_args()
    if args.data:
        global DATA
        DATA = Path(args.data).resolve()

    DATA.mkdir(parents=True, exist_ok=True)
    topics = all_topics()
    (DATA / "all_topics.json").write_text(json.dumps(topics, indent=1), encoding="utf-8")
    chosen = sample_topics(topics, args.per_domain, args.seed)
    (DATA / "sample.json").write_text(json.dumps(chosen, indent=1), encoding="utf-8")
    print(f"{len(topics)} topics; sampled {len(chosen)} ({args.per_domain} per domain)", flush=True)

    sampled = [t["id"] for t in chosen]
    for cutoff in CUTOFFS:
        out_dir = DATA / "topics" / str(cutoff)
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, t in enumerate(chosen, 1):
            path = out_dir / f"{t['id']}.json"
            if path.exists():
                continue
            try:
                rec = collect_topic(t["id"], cutoff, sampled)
            except oa.BudgetExhausted as e:
                print(f"stopped: {e}", flush=True)
                print(f"progress kept: rerun the same command to continue from topic {i}.", flush=True)
                return
            path.write_text(json.dumps(rec), encoding="utf-8")
            print(f"[{cutoff}] {i}/{len(chosen)} {t['id']} size={rec['size']} "
                  f"citers train={len(rec['cited_by_train'])} test={len(rec['cited_by_test'])}",
                  flush=True)


if __name__ == "__main__":
    main()
