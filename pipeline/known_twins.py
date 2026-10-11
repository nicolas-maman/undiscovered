"""Known twins (research/KNOWN-TWINS.md): the benchmark's papers in describing units, and the result.

    pip install numpy scikit-learn wordfreq       # this script only
    python pipeline/known_twins.py units <distill-2025 checkout>      # once: add the units
    python pipeline/known_twins.py result <distill-2025 checkout>     # whenever: the result, or how far off it is

`units` reads the benchmark's link list at a pinned commit, finds each paper
in OpenAlex, keeps those with a usable abstract, and appends units holding
them to the branch's units/index.json, mixed with papers of the 2025 set,
five volunteers each. Units already there are not changed. It writes
known-twins.json: each paper kept, its family, field, role and the text it
was judged on (OpenAlex, CC0), with the benchmark's credit (CC BY 4.0).

`result` computes the measures of the plan from the branch's results once
every paper kept has descriptions from at least three different models, and
says how many are still short otherwise. An OpenAlex key, if any, is read
from OPENALEX_API_KEY.
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "clients" / "python"))
sys.path.insert(0, str(ROOT / "pipeline"))
import distill_units  # noqa: E402
from undiscovered.mapper import usable  # noqa: E402
from undiscovered.openalex import abstract_text  # noqa: E402

COMMIT = "912badb32eff3c07926ab36f8b050a6d630e5a42"
LINKS = (f"https://raw.githubusercontent.com/ErykKul/same-problem-different-field/{COMMIT}"
         "/datasets/mode_a_seed_families.csv")
CREDIT = ("Kulikowski, E. (2026). Same Problem, Different Field: Cross-Domain Solution Import via "
          "Domain-Stripped Computational Fingerprints. arXiv:2609.07595. Benchmark: "
          f"https://github.com/ErykKul/same-problem-different-field at {COMMIT}, CC BY 4.0, "
          "https://doi.org/10.48804/W3B9WC")
QUORUM = 5
PER_UNIT = 5                # benchmark papers in a unit; the rest are papers of the 2025 set
SEED = 2026
MIN_MODELS = 3              # different models every paper needs before the result is computed
BOOTSTRAP = 2000


def openalex_ref(url: str) -> str | None:
    """How to look a benchmark paper up in OpenAlex: arXiv (new or old identifiers), PMC or DOI."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([a-z\-]+/[0-9]{7}|[0-9]{4}\.[0-9]{4,5})", url)
    if m:
        return f"doi:10.48550/arxiv.{m.group(1)}"
    m = re.search(r"(PMC[0-9]+)", url)
    if m:
        return f"pmcid:{m.group(1)}"
    m = re.search(r"doi\.org/(10\..+)$", url)
    return f"doi:{m.group(1)}" if m else None


def benchmark(get=requests.get) -> list[dict]:
    text = get(LINKS, timeout=60).text
    return list(csv.DictReader(line for line in io.StringIO(text) if not line.startswith("#")))


def resolve(rows: list[dict], key: str = "", get=requests.get) -> list[dict]:
    """The benchmark papers OpenAlex has with a usable abstract, with what they will be judged on."""
    kept = []
    for r in rows:
        ref = openalex_ref(r["url"])
        if not ref:
            continue
        params = {"select": "id,title,abstract_inverted_index,primary_topic"}
        if key:
            params["api_key"] = key
        resp = get(f"https://api.openalex.org/works/{ref}", params=params, timeout=60)
        time.sleep(0.15)
        if resp.status_code != 200:
            continue
        w = resp.json()
        text = f"{(w.get('title') or '').strip()}. {abstract_text(w.get('abstract_inverted_index'))}"
        if not usable(text):
            continue
        topic = w.get("primary_topic") or {}
        kept.append({"id": r["id"], "work": w["id"].rsplit("/", 1)[-1], "family": r["family"], "field": r["field"],
                     "role": r["role"], "method_named": r.get("method_named", ""), "text": text,
                     "domain": (topic.get("domain") or {}).get("display_name", "")})
    return kept


def add_units(index: dict, gold: list[dict], avoid: dict[str, list[str]], ordinary: list[str],
              ordinary_avoid: dict[str, list[str]]) -> list[dict]:
    """Units of twenty holding PER_UNIT benchmark papers each, the rest ordinary papers, in a fixed order."""
    rng = random.Random(SEED)
    works = sorted(g["work"] for g in gold)
    rng.shuffle(works)
    pool = sorted(ordinary)
    rng.shuffle(pool)
    first = max(int(u["unit"][2:]) for u in index["units"]) + 1
    template = index["units"][0]
    units = []
    for i, k in enumerate(range(0, len(works), PER_UNIT)):
        mine = works[k:k + PER_UNIT]
        filler = pool[i * (distill_units.UNIT_SIZE - PER_UNIT):(i + 1) * (distill_units.UNIT_SIZE - PER_UNIT)]
        unit_works = mine + filler
        rng.shuffle(unit_works)
        units.append({"unit": f"u-{first + i:06d}", "protocol": 0, "kind": "distill", "works": unit_works,
                      "avoid": {w: (avoid.get(w) or ordinary_avoid.get(w, [])) for w in unit_works},
                      "max_avoided": template["max_avoided"], "instructions": template["instructions"],
                      "quorum": QUORUM, "status": "open"})
    return units


def make_units(branch: Path, key: str = "") -> None:
    index = json.loads((branch / "units" / "index.json").read_text(encoding="utf-8"))
    if (branch / "known-twins.json").exists():
        raise SystemExit("known-twins.json is already there: the units were added before")
    papers = json.loads((branch / "papers.json").read_text(encoding="utf-8"))
    gold = [g for g in resolve(benchmark(), key) if g["work"] not in papers]
    texts, ids = {}, sorted(papers)
    for k in range(0, len(ids), 50):         # the 2025 set's texts, so words are weighed against the same corpus
        params = {"filter": "openalex:" + "|".join(ids[k:k + 50]), "per_page": 50,
                  "select": "id,title,abstract_inverted_index"}
        if key:
            params["api_key"] = key
        for w in requests.get("https://api.openalex.org/works", params=params, timeout=90).json()["results"]:
            texts[w["id"].rsplit("/", 1)[-1]] = (f"{(w.get('title') or '').strip()}. "
                                                f"{abstract_text(w.get('abstract_inverted_index'))}")
        time.sleep(0.2)
    texts.update({g["work"]: g["text"] for g in gold})
    domain = {w: p["domain"] for w, p in papers.items() if w in texts}
    domain.update({g["work"]: g["domain"] or "Physical Sciences" for g in gold})
    avoid = distill_units.distinctive(texts, domain)
    ordinary_avoid = {w: a for u in index["units"] for w, a in u["avoid"].items()}
    new = add_units(index, gold, {g["work"]: avoid[g["work"]] for g in gold}, list(papers), ordinary_avoid)
    index["units"] += new
    index["papers"] = len(papers) + len(gold)
    (branch / "units" / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    for g in gold:                          # so the combining job knows their domain like any other paper's
        papers[g["work"]] = {"topic": "", "topic_name": "", "subfield": "", "field": g["field"].replace("_", " "),
                             "domain": g["domain"], "benchmark": "known twins"}
    (branch / "papers.json").write_text(json.dumps(papers, indent=1, sort_keys=True), encoding="utf-8")
    (branch / "known-twins.json").write_text(json.dumps(
        {"credit": CREDIT, "plan": "https://github.com/nicolas-maman/undiscovered/blob/main/research/KNOWN-TWINS.md",
         "units": [u["unit"] for u in new], "papers": gold}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(gold)} benchmark papers in {len(new)} new units ({new[0]['unit']} to {new[-1]['unit']})")


def average_precision(order: list[str], relevant: set[str]) -> float:
    hits, total = 0, 0.0
    for rank, w in enumerate(order, 1):
        if w in relevant:
            hits += 1
            total += hits / rank
    return total / len(relevant) if relevant else float("nan")


def scores(vectors: dict[str, "object"], gold: list[dict]) -> dict[str, dict]:
    """For each query paper: its average precision and whether its nearest paper is a twin."""
    import numpy as np
    works = [g["work"] for g in gold if g["work"] in vectors]
    info = {g["work"]: g for g in gold}
    V = np.vstack([vectors[w] for w in works])
    S = V @ V.T
    out = {}
    for i, w in enumerate(works):
        g = info[w]
        if g["role"] != "member":
            continue
        twins = {x for x in works if x != w and info[x]["role"] == "member"
                 and info[x]["family"] == g["family"] and info[x]["field"] != g["field"]}
        if not twins:
            continue
        others = [j for j in range(len(works)) if j != i]
        order = [works[j] for j in sorted(others, key=lambda j: (-S[i, j], works[j]))]
        out[w] = {"ap": average_precision(order, twins), "top1": float(order[0] in twins),
                  "family": g["family"], "named": g["method_named"]}
    return out


def tfidf(texts: dict[str, str]) -> dict[str, "object"]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    works = sorted(texts)
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2).fit_transform([texts[w] for w in works])
    return {w: X[k].toarray().ravel() for k, w in enumerate(works)}


def described(branch: Path, gold: list[dict]) -> tuple[dict[str, list[dict]], dict[str, set]]:
    works = {g["work"] for g in gold}
    out, models = defaultdict(list), defaultdict(set)
    for f in sorted((branch / "results").glob("*/*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        for d in r["descriptions"]:
            if d["work"] in works:
                out[d["work"]].append({**d, "model": r["model"]["id"]})
                models[d["work"]].add((r["model"]["provider"], r["model"]["id"]))
    return out, models


def result(branch: Path) -> dict:
    import numpy as np
    gold = json.loads((branch / "known-twins.json").read_text(encoding="utf-8"))["papers"]
    descs, models = described(branch, gold)
    short = [g["work"] for g in gold if len(models.get(g["work"], ())) < MIN_MODELS]
    if short:
        return {"status": "waiting", "papers": len(gold), "short_of_models": len(short),
                "note": f"{len(short)} of {len(gold)} papers have descriptions from fewer than {MIN_MODELS} models"}
    abstracts = tfidf({g["work"]: g["text"] for g in gold})
    flat = [(w, d) for w, ds in descs.items() for d in ds]
    from sklearn.feature_extraction.text import TfidfVectorizer
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2).fit_transform(
        [f"{d['problem']} {d['approach']}" for _, d in flat])
    by_work = defaultdict(list)
    for k, (w, _) in enumerate(flat):
        by_work[w].append(k)
    desc_vec = {}
    for w, ks in by_work.items():
        v = np.asarray(X[ks].mean(axis=0)).ravel()
        desc_vec[w] = v / (np.linalg.norm(v) or 1.0)
    a, d = scores(abstracts, gold), scores(desc_vec, gold)
    queries = sorted(set(a) & set(d))
    families = sorted({a[q]["family"] for q in queries})
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(BOOTSTRAP):
        draw = rng.choice(families, len(families))
        qs = [q for f in draw for q in queries if a[q]["family"] == f]
        diffs.append(np.mean([d[q]["ap"] for q in qs]) - np.mean([a[q]["ap"] for q in qs]))

    def summary(s: dict, qs: list[str]) -> dict:
        return {"map": round(float(np.mean([s[q]["ap"] for q in qs])), 4),
                "precision_at_1": round(float(np.mean([s[q]["top1"] for q in qs])), 4)} if qs else {}

    unnamed = [q for q in queries if a[q]["named"] == "no"]
    diff = float(np.mean([d[q]["ap"] for q in queries]) - np.mean([a[q]["ap"] for q in queries]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"status": "complete", "queries": len(queries), "families": len(families),
            "abstracts": summary(a, queries), "descriptions": summary(d, queries),
            "difference": round(diff, 4), "difference_ci": [round(float(lo), 4), round(float(hi), 4)],
            "holds": bool(lo > 0),
            "unnamed": {"queries": len(unnamed), "abstracts": summary(a, unnamed), "descriptions": summary(d, unnamed)},
            "models": per_model(descs, gold, abstracts)}


def per_model(descs: dict[str, list[dict]], gold: list[dict], abstracts: dict) -> list[dict]:
    """For each model that described at least 30 of the papers: its MAP and the abstracts' on those papers."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    by_model = defaultdict(dict)
    for w, ds in descs.items():
        for x in ds:
            by_model[x["model"]].setdefault(w, f"{x['problem']} {x['approach']}")
    out = []
    for model, texts in sorted(by_model.items()):
        if len(texts) < 30:
            continue
        mine = [g for g in gold if g["work"] in texts]
        works = sorted(texts)
        X = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2).fit_transform([texts[w] for w in works])
        d = scores({w: X[k].toarray().ravel() for k, w in enumerate(works)}, mine)
        a = scores({w: abstracts[w] for w in works}, mine)
        qs = sorted(set(a) & set(d))
        if qs:
            out.append({"model": model, "papers": len(texts), "queries": len(qs),
                        "descriptions_map": round(float(np.mean([d[q]["ap"] for q in qs])), 4),
                        "abstracts_map": round(float(np.mean([a[q]["ap"] for q in qs])), 4)})
    return out


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("units", "result"):
        raise SystemExit(__doc__)
    branch = Path(sys.argv[2])
    if sys.argv[1] == "units":
        make_units(branch, os.environ.get("OPENALEX_API_KEY", ""))
    elif not (branch / "known-twins.json").exists():
        print("no known twins on this branch")
    else:
        out = result(branch)
        (branch / "combined").mkdir(exist_ok=True)
        (branch / "combined" / "known-twins-result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
