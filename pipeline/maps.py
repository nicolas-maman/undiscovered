"""Two maps of the describing set for the site: by abstract, and by plain description.

    python pipeline/maps.py <distill-2025 checkout>

Reads papers.json, abstracts.jsonl and, when there are any,
combined/descriptions.jsonl, and writes combined/map.json. Each map places
every paper so that papers whose texts are alike sit close together: TF-IDF
of the text (English stop words removed, sublinear term frequency), reduced
to 50 dimensions, then laid out in two by t-SNE with a fixed seed.

The abstract map shows the literature as its fields write it: papers cluster
by field, because fields use their own words. The description map places the
same papers by what volunteers' models say they do, starting from where they
sit on the abstract map, so the site can show how far each paper moves once
its field's words are taken away. Known twins, the benchmark's papers that do
the same computation in different fields, should sit apart on the first map
and together on the second if the descriptions work.

The abstract map changes only when the set does, so it is kept and reused
while papers.json and abstracts.jsonl are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE

SEED = 2026
DIMS = 50
SCALE = 1000          # coordinates are 0 to SCALE, rounded to a tenth
TITLE = 140           # characters of a title kept for the map
MIN_DESCRIBED = 50    # fewer described papers than this: no description map yet


def layout(texts: list[str], init: np.ndarray | None = None) -> np.ndarray:
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2).fit_transform(texts)
    dims = min(DIMS, X.shape[1] - 1, X.shape[0] - 1)
    Z = TruncatedSVD(dims, random_state=SEED).fit_transform(X)
    perplexity = min(30.0, (len(texts) - 1) / 3)
    xy = TSNE(2, perplexity=perplexity, init="pca" if init is None else init, random_state=SEED,
              learning_rate="auto").fit_transform(Z)
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    return np.round((xy - lo) / np.maximum(hi - lo, 1e-9) * SCALE, 1)


def digest(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def maps(branch: Path) -> dict:
    papers = json.loads((branch / "papers.json").read_text(encoding="utf-8"))
    rows = {json.loads(line)["work"]: json.loads(line)
            for line in (branch / "abstracts.jsonl").read_text(encoding="utf-8").splitlines()}
    twins = branch / "known-twins.json"
    family = {p["work"]: p["family"] for p in json.loads(twins.read_text(encoding="utf-8"))["papers"]
              if p["role"] == "member"} if twins.exists() else {}
    works = sorted(w for w in papers if rows.get(w, {}).get("abstract"))
    fields = sorted({papers[w].get("field") or "" for w in works})
    domains = sorted({papers[w].get("domain") or "" for w in works})
    out_path = branch / "combined" / "map.json"
    out_path.parent.mkdir(exist_ok=True)
    key = digest(branch / "papers.json", branch / "abstracts.jsonl")
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    if old.get("key") == key and old.get("works") == works:
        abstract_xy = np.array(old["layouts"]["abstracts"], dtype=float)
    else:
        abstract_xy = layout([f"{rows[w]['title']} {rows[w]['abstract']}" for w in works])

    described: dict[str, list[str]] = {}
    index = branch / "combined" / "descriptions.jsonl"
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            described[r["work"]] = [f"{d['problem']} {d['approach']}" for d in r["descriptions"]]
    plain = [w for w in works if w in described]
    plain_xy = None
    if len(plain) >= MIN_DESCRIBED:
        at = {w: i for i, w in enumerate(works)}
        start = abstract_xy[[at[w] for w in plain]] / SCALE * 1e-4      # t-SNE wants a small initial spread
        plain_xy = layout([" ".join(described[w]) for w in plain], init=start)

    plain_at = {w: i for i, w in enumerate(plain)}
    out = {"key": key, "works": works, "fields": fields, "domains": domains,
           "papers": [[w, fields.index(papers[w].get("field") or ""), domains.index(papers[w].get("domain") or ""),
                       rows[w]["title"][:TITLE], rows[w].get("year"), family.get(w, "")] for w in works],
           "layouts": {"abstracts": abstract_xy.tolist(),
                       "descriptions": [plain_xy[plain_at[w]].tolist() if plain_xy is not None and w in plain_at
                                        else None for w in works]},
           "described": len(plain)}
    out_path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return {"papers": len(works), "described": len(plain), "description_map": plain_xy is not None}


if __name__ == "__main__":
    print(json.dumps(maps(Path(sys.argv[1]))))
