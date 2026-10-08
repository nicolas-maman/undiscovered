"""The stricter label: new links that a misfiled paper cannot explain.

OpenAlex files each work under topics with a language model that reads its
title, abstract and journal name. A paper that really belongs to topic B but
is filed under topic A still cites B's papers, so it shows up as a link from
A to B. Such mistakes are likelier between topics whose papers read alike,
which is exactly what the content features measure, so they could make
content look predictive for the wrong reason.

The stricter label counts, for each 2017 pair that connected, only the
citing works that are articles or reviews and that OpenAlex does not also
file under the other topic's subfield (each work has up to three topics).
It is fetched during the analysis, for the pairs that connected only (a
pair that did not connect under the main label cannot under this one).
"""

from __future__ import annotations

from . import openalex as oa


def _count(citing: str, instrument: list[str], window: tuple[int, int], other_subfield: str) -> int:
    flt = (f"primary_topic.id:{citing},referenced_works:{'|'.join(instrument)},"
           f"publication_year:{window[0]}-{window[1]},type:article|review")
    n = 0
    for page in oa.paged("works", {"filter": flt, "per_page": 200, "select": "id,topics"}):
        for w in page["results"]:
            subfields = {((t.get("subfield") or {}).get("display_name")) for t in w.get("topics") or []}
            if other_subfield not in subfields:
                n += 1
    return n


def collect(ev: dict, min_test_links: int) -> dict[tuple[str, str], int]:
    """Strict link counts for the evaluation pairs that connected."""
    recs, subfield = ev["recs"], ev["subfields"]
    out: dict[tuple[str, str], int] = {}
    todo = [(p, d) for p, d, y in zip(ev["pairs"], ev["directions"], ev["labels"]) if y]
    for i, ((a, b), (ab, ba)) in enumerate(todo, 1):
        window = tuple(recs[a]["test_window"])
        n = 0
        try:
            if ab:      # works in a citing b's reference papers
                n += _count(a, recs[b]["instrument"], window, subfield[b])
            if ba:
                n += _count(b, recs[a]["instrument"], window, subfield[a])
        except oa.BudgetExhausted as e:
            raise SystemExit(f"stopped after {i - 1} of {len(todo)} pairs for the strict label: {e}\n"
                             "Rerun the same command; what was fetched is cached.") from e
        out[(a, b)] = n
        if i % 100 == 0:
            print(f"strict label: {i}/{len(todo)} pairs", flush=True)
    return out
