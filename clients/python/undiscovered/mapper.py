"""Map units: one topic's citation record at a freeze year, with no AI model.

The record has the same meaning as the research collector's
(``research/undiscovered_research/collect.py``), so the network model the
first test validated can rank the map. Three differences, because the map
covers every topic rather than a sample: the years before the train window
are counted for every citing topic, there is no test window yet, and only
the number of usable abstracts is kept, not their text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone

from .openalex import OpenAlex, short_id, abstract_text
from .stopwords import ENGLISH_STOP_WORDS

FORMAT = 1
TRAIN_YEARS = 7                 # train window [F-7, F]: eight calendar years
RECENT_YEARS = 3                # its last three
INSTRUMENT = 100                # reference papers per topic
CANDIDATES = 400                # most cited today, among which they are chosen
ABSTRACTS = 40
SAMPLE_SEED = 17
MIN_WORDS = 40
MIN_ENGLISH_SHARE = 0.25


def usable(text: str) -> bool:
    """An English text long enough to say what the paper is about (as in the research code)."""
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < MIN_WORDS:
        return False
    return sum(w in ENGLISH_STOP_WORDS for w in words) / len(words) >= MIN_ENGLISH_SHARE


def citations_up_to(work: dict, year: int) -> int:
    later = sum(c.get("cited_by_count", 0) for c in work.get("counts_by_year") or []
                if c.get("year", 0) > year)
    return max(0, int(work.get("cited_by_count") or 0) - later)


def reference_papers(api: OpenAlex, topic: str, freeze: int) -> list[str]:
    """The topic's 100 papers most cited up to the end of the freeze year."""
    candidates: list[dict] = []
    for page in api.paged("works", {
            "filter": f"primary_topic.id:{topic},publication_year:<{freeze + 1}",
            "sort": "cited_by_count:desc", "per_page": 200,
            "select": "id,cited_by_count,counts_by_year"}):
        candidates.extend(page["results"])
        if len(candidates) >= CANDIDATES:
            break
    ranked = sorted(candidates[:CANDIDATES],
                    key=lambda w: (-citations_up_to(w, freeze), short_id(w["id"])))
    return [short_id(w["id"]) for w in ranked[:INSTRUMENT] if citations_up_to(w, freeze) > 0]


def citing_counts(api: OpenAlex, instrument: list[str], start: int | None, end: int) -> dict[str, int]:
    """Works published in [start, end] citing any reference paper, by primary topic."""
    if not instrument:
        return {}
    years = f"<{end + 1}" if start is None else f"{start}-{end}"
    flt = f"referenced_works:{'|'.join(instrument)},publication_year:{years}"
    counts: dict[str, int] = {}
    for page in api.paged("works", {"filter": flt, "group_by": "primary_topic.id", "per_page": 200}):
        for g in page.get("group_by", []):
            if g.get("key") and g["key"] != "unknown":
                counts[short_id(g["key"])] = int(g["count"])
    return counts


def map_topic(api: OpenAlex, topic: str, freeze: int) -> dict:
    train = (freeze - TRAIN_YEARS, freeze)
    recent = (freeze - RECENT_YEARS + 1, freeze)
    instrument = reference_papers(api, topic, freeze)
    years = api.get("works", {"filter": f"primary_topic.id:{topic},publication_year:{train[0]}-{train[1]}",
                              "group_by": "publication_year", "per_page": 200})
    by_year = {str(g["key"]): int(g["count"]) for g in years.get("group_by", []) if g.get("key")}
    sample = api.get("works", {
        "filter": f"primary_topic.id:{topic},publication_year:{train[0]}-{train[1]},has_abstract:true",
        "sample": ABSTRACTS, "seed": SAMPLE_SEED, "per_page": ABSTRACTS,
        "select": "id,title,abstract_inverted_index"})
    texts = [f"{w.get('title') or ''}. {abstract_text(w.get('abstract_inverted_index'))}".strip()
             for w in sample["results"]]
    return {
        "format": FORMAT,
        "topic": topic,
        "freeze": freeze,
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "train_window": list(train),
        "recent_window": list(recent),
        "size": sum(by_year.values()),
        "works_by_year": by_year,
        "instrument": instrument,
        "usable_abstracts": sum(usable(t) for t in texts),
        "cited_by_train": citing_counts(api, instrument, *train),
        "cited_by_recent": citing_counts(api, instrument, *recent),
        "cited_by_before": citing_counts(api, instrument, None, train[0] - 1),
    }


def map_unit(api: OpenAlex, unit: dict, progress: Callable[[str], None] = print) -> list[dict]:
    records = []
    for i, topic in enumerate(unit["topics"], 1):
        records.append(map_topic(api, topic, unit["freeze"]))
        left = "" if api.remaining is None else f", OpenAlex calls left today: {api.remaining}"
        progress(f"  {unit['unit']}: topic {i}/{len(unit['topics'])} {topic}{left}")
    return records
