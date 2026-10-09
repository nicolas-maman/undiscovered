"""Write the backtest's pairs as plain tables, for any language or spreadsheet.

    python -m undiscovered_research.export

writes ``results/pairs_2011.csv`` and ``results/pairs_2017.csv``: one row per
eligible pair of topics, with who they are, every feature the models use,
the links before and after the freeze, the label, and at 2017 the stricter
label and each model's score. ``docs/DATA.md`` says what every column means.
The same numbers as the published report, from the same code and data.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from . import backtest, collect, embed, strict
from . import openalex as oa
from .gentle import be_gentle

ID_COLUMNS = ["topic_a", "topic_b", "name_a", "name_b", "field_a", "field_b", "domain_a", "domain_b"]
LINK_COLUMNS = ["prior_link_count", "links_a_to_b", "links_b_to_a", "links_after", "connected"]


def rows(table: dict, scores: dict | None = None, strict_links: dict | None = None,
         min_test_links: int = 3) -> list[dict]:
    out = []
    for i, (a, b) in enumerate(table["pairs"]):
        ab, ba = table["directions"][i]
        row = {
            "topic_a": a, "topic_b": b,
            "name_a": table["names"][a], "name_b": table["names"][b],
            "field_a": table["fields"][a], "field_b": table["fields"][b],
            "domain_a": table["domains"][a], "domain_b": table["domains"][b],
            "prior_link_count": table["links"][i][0],
            "links_a_to_b": ab, "links_b_to_a": ba,
            "links_after": table["links"][i][1],
            "connected": int(table["labels"][i]),
            **{f: table["rows"][i][f] for f in backtest.FEATURE_SETS["combined"]},
        }
        if strict_links is not None:
            n = strict_links.get((a, b), 0)
            row["strict_links_after"] = n
            row["connected_strict"] = int(n >= min_test_links)
        if scores is not None:
            for name, s in scores.items():
                row[f"score_{name}"] = float(s[i])
        out.append(row)
    return out


def write_csv(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="", help="folder for the tables (default research/results)")
    args = ap.parse_args()
    be_gentle()
    oa.CACHE_DIR = backtest.DATA / "cache"     # the stricter label is read from the analysis's cache
    model = embed.TFIDF
    fit = backtest.pair_table(backtest.TRAIN_CUTOFF, 1, 3, model)
    ev = backtest.pair_table(backtest.EVAL_CUTOFF, 1, 3, model)
    scores = {}
    for name, cols in backtest.FEATURE_SETS.items():
        scores[name], _ = backtest.fit_score(backtest.matrix(fit["rows"], cols), fit["labels"],
                                             backtest.matrix(ev["rows"], cols))
    out = Path(args.out) if args.out else backtest.RESULTS
    write_csv(out / f"pairs_{backtest.TRAIN_CUTOFF}.csv", rows(fit))
    write_csv(out / f"pairs_{backtest.EVAL_CUTOFF}.csv", rows(ev, scores, strict.collect(ev, 3)))
    print(f"wrote {len(fit['pairs'])} and {len(ev['pairs'])} pairs to {out}")


if __name__ == "__main__":
    main()
