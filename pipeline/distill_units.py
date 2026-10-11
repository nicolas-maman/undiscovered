"""Make the describing (distill) units: the papers the crowd describes first.

    pip install wordfreq        # this script only; clients never need it
    python pipeline/distill_units.py --sample research/data/sample.json --out <distill-2025 checkout>

The papers are the ones the map records already count: for each of the first
test's 300 topics, the 40 works with an abstract that OpenAlex samples (seed
17) from the eight years up to 2025, kept when the abstract is usable (the
same rule as the backtest) and the work is research (an article, review,
preprint, conference paper or abstract, book or chapter, dissertation or
report; not a dataset, editorial, erratum, peer review and the like). That
is one request per topic; an OpenAlex key, if any, is read from
OPENALEX_API_KEY.

For each paper the unit lists its most distinctive words: the highest TF-IDF
scores of its title and abstract against all the papers, leaving out words
that belong to no field. A word is a field's when it is rare in everyday
English (wordfreq's Zipf frequency under 4, as for "gyrase" or "proline"),
or, when it appears in at least 10 papers, when its papers are concentrated
in one or two of the four domains (as for "cancer", "students" or "soil").
Everyday words used everywhere ("combined", "training", "knowledge") are
left out, so a model is not told to avoid them, and so are words about the
document itself ("paper", "chapter"). The model is told not to use
the listed words, and the checking job counts how many it used anyway, so
"without the field's words" means the same thing to every model and every
client. The units mix topics, twenty papers to a unit, and each needs results
from two volunteers. Writes units/index.json and papers.json (each paper's
topic and domain) under --out.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "clients" / "python"))
from undiscovered.openalex import abstract_text  # noqa: E402
from undiscovered.mapper import ABSTRACTS, SAMPLE_SEED, TRAIN_YEARS, usable  # noqa: E402
from undiscovered.stopwords import ENGLISH_STOP_WORDS  # noqa: E402

FREEZE = 2025
UNIT_SIZE = 20
FIRST_UNIT = 100001         # map units are u-000001 to u-000452
AVOID = 8                   # distinctive words listed per paper
EVERYDAY = 4.0              # Zipf frequency in English from which a word is everyday, not a field's
ENOUGH = 10                 # papers a word must appear in before its spread across domains is judged
CONCENTRATED = 0.8          # share of its (size-adjusted) use in its two main domains that makes it a field's
# Words about the document rather than its field, never listed.
DOCUMENT = {"abstract", "article", "articles", "author", "authors", "book", "books", "chapter", "chapters",
            "paper", "papers", "report", "review", "study", "studies", "thesis"}
RESEARCH = {"article", "review", "preprint", "conference-paper", "conference-abstract", "book-chapter",
            "book", "dissertation", "report"}
MAX_AVOIDED = 2             # of them a description may still use (provisional: set on the first trial runs)
QUORUM = 2
SEED = 2025
WORD = re.compile(r"[^\W\d_]+")
INSTRUCTIONS = ("Describe the problem this work addresses and how it goes about it, so that a researcher "
                "in any field would recognise the problem. Do not name the field, its methods or its "
                "objects of study, and do not reuse terms from the abstract that only that field would use.")


def sample_works(topic: str, key: str = "") -> list[dict]:
    """The topic's sampled works with usable abstracts, as the map records count them."""
    params = {"filter": f"primary_topic.id:{topic},publication_year:{FREEZE - TRAIN_YEARS}-{FREEZE},"
                        "has_abstract:true",
              "sample": ABSTRACTS, "seed": SAMPLE_SEED, "per_page": ABSTRACTS,
              "select": "id,type,title,abstract_inverted_index"}
    if key:
        params["api_key"] = key
    for attempt in range(6):
        resp = requests.get("https://api.openalex.org/works", params=params, timeout=90)
        if resp.status_code == 200:
            break
        time.sleep(2 ** attempt)
    else:
        raise SystemExit(f"OpenAlex kept failing for {topic} (HTTP {resp.status_code})")
    out = []
    for w in resp.json().get("results", []):
        if w.get("type") not in RESEARCH:
            continue
        title = (w.get("title") or "").strip()
        abstract = abstract_text(w.get("abstract_inverted_index"))
        if usable(f"{title}. {abstract}"):
            out.append({"id": w["id"].rsplit("/", 1)[-1], "text": f"{title}. {abstract}"})
    return out


def terms(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if len(w) >= 3 and w not in ENGLISH_STOP_WORDS]


def zipf(word: str) -> float:
    from wordfreq import zipf_frequency
    return zipf_frequency(word, "en")


def fields_words(counts: dict[str, Counter], domain: dict[str, str], everyday=zipf) -> set[str]:
    """The words that belong to some field rather than to everyday English (see the module's text)."""
    size = Counter(domain[w] for w in counts)
    by_domain: dict[str, Counter] = {}
    for wid, c in counts.items():
        for word in c:
            by_domain.setdefault(word, Counter())[domain[wid]] += 1
    out = set()
    for word, spread in by_domain.items():
        if word in DOCUMENT:
            continue
        if sum(spread.values()) >= ENOUGH:
            rates = sorted((spread[d] / size[d] for d in size), reverse=True)
            if sum(rates[:2]) >= CONCENTRATED * sum(rates):
                out.add(word)
        elif everyday(word) < EVERYDAY:
            out.add(word)
    return out


def distinctive(papers: dict[str, str], domain: dict[str, str], k: int = AVOID,
                everyday=zipf) -> dict[str, list[str]]:
    """Each paper's k field words with the highest TF-IDF against all the papers; ties by the word."""
    counts = {wid: Counter(terms(text)) for wid, text in papers.items()}
    df = Counter(w for c in counts.values() for w in c)
    keep = fields_words(counts, domain, everyday)
    n = len(papers)
    out = {}
    for wid, c in counts.items():
        score = {w: tf * math.log(n / df[w]) for w, tf in c.items() if w in keep}
        out[wid] = sorted(score, key=lambda w: (-score[w], w))[:k]
    return out


def make_units(papers: dict[str, dict], avoid: dict[str, list[str]]) -> dict:
    ids = sorted(papers)
    random.Random(SEED).shuffle(ids)
    units = []
    for i, k in enumerate(range(0, len(ids), UNIT_SIZE)):
        works = ids[k:k + UNIT_SIZE]
        units.append({"unit": f"u-{FIRST_UNIT + i:06d}", "protocol": 0, "kind": "distill", "works": works,
                      "avoid": {w: avoid[w] for w in works}, "max_avoided": MAX_AVOIDED,
                      "instructions": INSTRUCTIONS, "quorum": QUORUM, "status": "open"})
    rule = {"avoid": AVOID, "document_words": sorted(DOCUMENT), "everyday_zipf": EVERYDAY, "spread_from_papers": ENOUGH,
            "concentrated_share": CONCENTRATED, "max_avoided": MAX_AVOIDED, "research_types": sorted(RESEARCH)}
    return {"set": f"distill-{FREEZE}", "papers": len(ids), "rule": rule, "units": units}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample", required=True, help="the first test's sample.json")
    ap.add_argument("--out", required=True, help="a checkout of the distill-2025 branch")
    args = ap.parse_args()
    topics = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    papers, texts = {}, {}
    for i, t in enumerate(topics, 1):
        for w in sample_works(t["id"], os.environ.get("OPENALEX_API_KEY", "")):
            if w["id"] not in papers:           # a work is sampled under its primary topic only
                papers[w["id"]] = {"topic": t["id"], "domain": t["domain"]}
                texts[w["id"]] = w["text"]
        print(f"{i}/{len(topics)} {t['id']}: {len(papers)} papers so far", flush=True)
        time.sleep(0.25)
    index = make_units(papers, distinctive(texts, {w: p["domain"] for w, p in papers.items()}))
    out = Path(args.out)
    (out / "units").mkdir(parents=True, exist_ok=True)
    (out / "units" / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    (out / "papers.json").write_text(json.dumps(papers, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{index['papers']} papers in {len(index['units'])} units -> {out}")


if __name__ == "__main__":
    main()
