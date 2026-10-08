"""Collect everything the backtest needs from OpenAlex, per topic and cutoff.

For a cutoff year C (the literature is "frozen" at the end of C):

* train window = [C-7, C] (eight calendar years), test window = [C+1, C+6].
* Topics are OpenAlex *primary* topics throughout: a work counts once, under
  the topic it is most about, rather than under each of up to three topics.
* reference papers (``instrument`` in the records) = the topic's 100 papers
  published up to C with the most citations made up to C. OpenAlex sorts by
  today's citation count, so we take the 400 most cited today and subtract
  each paper's citations from the years after C (``counts_by_year``, which
  starts in 2012) before choosing. Ranking by today's counts would pick
  papers for citations they received later, partly from the very pairs the
  test asks about.
* A link from topic A to topic B in a window is the number of works whose
  primary topic is A, published in that window, that cite any of B's
  reference papers. One request (``group_by=primary_topic.id``) returns that
  count for every citing topic at once.
* train window and its last three years: the full distribution over all
  citing topics (cursor-paged), because the network features need each
  topic's whole neighbourhood, now and recently.
* earlier years and the test window: only the citing topics in the sample,
  asked in chunks of 100 (the OR limit). They only concern sampled pairs.
* abstracts = a random sample (OpenAlex ``sample`` + ``seed``) of the topic's
  papers in the train window that have an abstract. Random rather than most
  cited, because citation counts include citations made after the cutoff.
* works by year = the topic's works per year in the train window, which give
  its size and how fast it grew.

Everything lands in ``research/data/topics/<cutoff>/<topic>.json``. Records
from an older version of this code are collected again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import cleanup
from . import openalex as oa
from .gentle import be_gentle

DATA = Path(__file__).resolve().parent.parent / "data"
FORMAT = 2                      # version of the record layout; older records are collected again
CUTOFFS = (2011, 2017)          # 2011 fits the models; 2017 is the evaluation
TRAIN_YEARS = 7                 # train window [C-7, C]
TEST_YEARS = 6                  # test window  [C+1, C+6]
RECENT_YEARS = 3                # the last years of the train window, for recent neighbourhoods
INSTRUMENT = 100                # reference papers per topic
CANDIDATES = 400                # most cited today, among which the reference papers are chosen
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


def sample_id(sampled: list[str]) -> str:
    """A short fingerprint of a topic sample. Records for one sample are no use for another."""
    return hashlib.sha256(",".join(sorted(sampled)).encode()).hexdigest()[:16]


def citations_up_to(work: dict, cutoff: int) -> int:
    """Citations a work had received by the end of ``cutoff``."""
    later = sum(c.get("cited_by_count", 0) for c in work.get("counts_by_year") or []
                if c.get("year", 0) > cutoff)
    return max(0, int(work.get("cited_by_count") or 0) - later)


def reference_papers(topic_id: str, cutoff: int) -> list[str]:
    """The topic's INSTRUMENT most cited papers, counting citations up to the cutoff."""
    candidates: list[dict] = []
    for page in oa.paged("works", {
            "filter": f"primary_topic.id:{topic_id},publication_year:<{cutoff + 1}",
            "sort": "cited_by_count:desc", "per_page": 200,
            "select": "id,cited_by_count,counts_by_year"}):
        candidates.extend(page["results"])
        if len(candidates) >= CANDIDATES:
            break
    # Ties are broken by id: today's count would bring later citations back in.
    ranked = sorted(candidates[:CANDIDATES],
                    key=lambda w: (-citations_up_to(w, cutoff), oa.short_id(w["id"])))
    return [oa.short_id(w["id"]) for w in ranked[:INSTRUMENT] if citations_up_to(w, cutoff) > 0]


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


def works_by_year(topic_id: str, start: int, end: int) -> dict[str, int]:
    page = oa.get("works", {"filter": f"primary_topic.id:{topic_id},publication_year:{start}-{end}",
                            "group_by": "publication_year", "per_page": 200})
    return {str(g["key"]): int(g["count"]) for g in page.get("group_by", []) if g.get("key")}


def collect_topic(topic_id: str, cutoff: int, sampled: list[str]) -> dict:
    train = (cutoff - TRAIN_YEARS, cutoff)
    test = (cutoff + 1, cutoff + TEST_YEARS)
    recent = (cutoff - RECENT_YEARS + 1, cutoff)

    instrument = reference_papers(topic_id, cutoff)
    by_year = works_by_year(topic_id, *train)

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

    def counts(start, end, only=None):
        return _citing_counts(instrument, start, end, only=only) if instrument else {}

    return {
        "format": FORMAT,
        # Earlier years and the test window are counted for this sample only.
        "sample": sample_id(sampled),
        "topic": topic_id,
        "cutoff": cutoff,
        # OpenAlex changes over time, and its seeded samples with it.
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "train_window": train,
        "test_window": test,
        "recent_window": recent,
        "size": sum(by_year.values()),
        "works_by_year": by_year,
        "instrument": instrument,
        "abstracts": abstracts,
        "cited_by_train": counts(*train),
        "cited_by_recent": counts(*recent),
        # Every year before the train window, for the sampled topics only: a
        # pair is "not yet connected" only if it was never linked before the
        # cutoff, as in Science4Cast, not merely quiet in the train window.
        "cited_by_before": counts(None, train[0] - 1, only=sampled),
        "cited_by_test": counts(*test, only=sampled),
    }


def is_current(path: Path, sample: str) -> bool:
    """Collected by this version of the code, for this sample."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return rec.get("format") == FORMAT and rec.get("sample") == sample


def load_or_draw_sample(per_domain: int, seed: int) -> list[dict]:
    """The data directory's sample: drawn once, then reused as it is.

    Drawing again later could give a different sample if OpenAlex added or
    removed topics in the meantime, and the records already collected would
    no longer match it.
    """
    meta_path, sample_path = DATA / "sample_meta.json", DATA / "sample.json"
    wanted = {"seed": seed, "per_domain": per_domain}
    if sample_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if {k: meta.get(k) for k in wanted} != wanted:
            raise SystemExit(f"{DATA} holds a sample drawn with {meta}; use another --data for {wanted}.")
        return json.loads(sample_path.read_text(encoding="utf-8"))
    topics = all_topics()
    (DATA / "all_topics.json").write_text(json.dumps(topics, indent=1), encoding="utf-8")
    chosen = sample_topics(topics, per_domain, seed)
    if sample_path.exists():            # from before sample_meta.json existed: must match
        old = json.loads(sample_path.read_text(encoding="utf-8"))
        if [t["id"] for t in old] != [t["id"] for t in chosen]:
            raise SystemExit(f"{sample_path} does not match a fresh draw with {wanted}; "
                             "use another --data.")
    sample_path.write_text(json.dumps(chosen, indent=1), encoding="utf-8")
    meta_path.write_text(json.dumps({**wanted, "topics": len(topics),
                                     "drawn": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                     "sample": sample_id([t["id"] for t in chosen])}, indent=1),
                         encoding="utf-8")
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--per-domain", type=int, default=75)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--data", default="", help="data directory (default research/data); "
                    "use a separate one for each topic sample")
    ap.add_argument("--keep-cache", action="store_true",
                    help="keep the OpenAlex response cache after the sample is complete")
    args = ap.parse_args()
    be_gentle()
    if args.data:
        global DATA
        DATA = Path(args.data).resolve()

    DATA.mkdir(parents=True, exist_ok=True)
    oa.CACHE_DIR = DATA / "cache"       # one cache per sample, deleted when the sample is complete
    chosen = load_or_draw_sample(args.per_domain, args.seed)
    print(f"sample of {len(chosen)} topics ({args.per_domain} per domain, seed {args.seed})", flush=True)
    print("Using your OpenAlex key." if oa.has_key else
          "No OpenAlex key: about 1,000 calls a day. A free key gives 10,000: "
          "https://openalex.org/settings/api", flush=True)

    sampled = [t["id"] for t in chosen]
    sample = sample_id(sampled)
    for cutoff in CUTOFFS:
        out_dir = DATA / "topics" / str(cutoff)
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, t in enumerate(chosen, 1):
            path = out_dir / f"{t['id']}.json"
            if is_current(path, sample):
                continue
            try:
                rec = collect_topic(t["id"], cutoff, sampled)
            except oa.BudgetExhausted as e:
                print(f"stopped: {e}", flush=True)
                print(f"progress kept: rerun the same command to continue from topic {i}.", flush=True)
                return
            path.write_text(json.dumps(rec), encoding="utf-8")
            left = "" if oa.remaining is None else f" (OpenAlex calls left today: {oa.remaining})"
            # Progress only. Nothing from the test window is printed: it is
            # the outcome, and nobody looks at outcomes before the analysis.
            print(f"[{cutoff}] {i}/{len(chosen)} {t['id']}{left}", flush=True)

    # Complete: the topic files hold everything, so the response cache is
    # only taking up disk.
    if not args.keep_cache:
        freed = cleanup.clean_response_cache(oa.CACHE_DIR)
        print(f"sample complete; removed the response cache ({freed / 1e6:.0f} MB)", flush=True)


if __name__ == "__main__":
    main()
