"""Offline tests: no network, no model download."""

from __future__ import annotations

import gzip
import json
import shutil

import numpy as np
import pytest

from undiscovered_research import backtest, cleanup, collect, embed, openalex, robustness


def test_abstract_text_rebuilds_word_order():
    inverted = {"fish": [0], "oil": [1], "thins": [2], "blood": [4], "the": [3]}
    assert openalex.abstract_text(inverted) == "fish oil thins the blood"
    assert openalex.abstract_text(None) == ""


def test_short_id():
    assert openalex.short_id("https://openalex.org/T10005") == "T10005"


def test_sample_topics_is_balanced_and_reproducible():
    topics = [{"id": f"T{i}", "domain": d} for i, d in
              enumerate(["Physical Sciences", "Life Sciences", "Health Sciences", "Social Sciences"] * 30)]
    a = collect.sample_topics(topics, 5, seed=7)
    b = collect.sample_topics(topics, 5, seed=7)
    assert [t["id"] for t in a] == [t["id"] for t in b]
    counts = {}
    for t in a:
        counts[t["domain"]] = counts.get(t["domain"], 0) + 1
    assert set(counts.values()) == {5}


def test_precision_at():
    y = np.array([1, 0, 1, 0])
    s = np.array([0.9, 0.8, 0.7, 0.1])
    assert backtest.precision_at(y, s, 1) == 1.0
    assert backtest.precision_at(y, s, 2) == 0.5


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Four topics in two domains; A-C stay apart, A-D connect after the cutoff,
    B-C were linked long before the train window and so are not "unconnected"."""
    topics = [
        {"id": "TA", "name": "a", "domain": "Life Sciences"},
        {"id": "TB", "name": "b", "domain": "Life Sciences"},
        {"id": "TC", "name": "c", "domain": "Physical Sciences"},
        {"id": "TD", "name": "d", "domain": "Physical Sciences"},
    ]
    (tmp_path / "sample.json").write_text(json.dumps(topics))
    citing = {  # topic -> (cited_by_before, cited_by_train, cited_by_test)
        "TA": ({"TC": 1}, {"TB": 9, "TX": 4}, {"TB": 9, "TD": 5}),
        "TB": ({}, {"TA": 7, "TX": 2}, {"TA": 6}),
        "TC": ({"TB": 4}, {"TD": 3}, {"TD": 3}),
        "TD": ({}, {"TC": 2, "TX": 1}, {"TC": 2}),
    }
    for cutoff in collect.CUTOFFS:
        d = tmp_path / "topics" / str(cutoff)
        d.mkdir(parents=True)
        for tid, (before, tr, te) in citing.items():
            d.joinpath(f"{tid}.json").write_text(json.dumps({
                "topic": tid, "size": 100, "instrument": ["W1"],
                "abstracts": [{"id": "W1", "text": "x"}],
                "cited_by_before": before, "cited_by_train": tr, "cited_by_test": te,
            }))
    monkeypatch.setattr(backtest, "DATA", tmp_path)
    vec = {"TA": [1.0, 0.0], "TB": [0.9, 0.1], "TC": [0.0, 1.0], "TD": [0.7, 0.7]}

    def fake_embeddings(cutoff, model, abstracts):
        out = {}
        for t in abstracts:
            v = np.array([vec[t]], dtype=np.float32)
            v /= np.linalg.norm(v)
            out[t] = {"vecs": v, "centroid": v[0]}
        return out

    monkeypatch.setattr(backtest, "topic_embeddings", fake_embeddings)
    return tmp_path


def test_pair_table_keeps_only_unconnected_cross_domain_pairs(world):
    table = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake")
    pairs = set(table["pairs"])
    assert ("TA", "TB") not in pairs                     # same domain
    assert ("TB", "TC") not in pairs                     # 4 citing works before the train window
    assert pairs == {("TA", "TC"), ("TA", "TD"), ("TB", "TD")}
    label = dict(zip(table["pairs"], table["labels"]))
    assert label[("TA", "TD")] == 1                      # 5 citing works after the cutoff
    assert label[("TA", "TC")] == 0
    links = dict(zip(table["pairs"], table["links"]))
    assert links[("TA", "TC")] == (1, 0)                 # one old link is still "unconnected"


def test_records_without_the_before_window_still_load(world):
    for p in (world / "topics" / "2017").glob("*.json"):
        rec = json.loads(p.read_text())
        del rec["cited_by_before"]
        p.write_text(json.dumps(rec))
    pairs = set(backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake")["pairs"])
    assert ("TB", "TC") in pairs


def test_pair_table_features_reflect_shared_citers(world):
    table = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake")
    rows = dict(zip(table["pairs"], table["rows"]))
    # TA and TD are both cited by TX; TA and TC share no citing topic.
    assert rows[("TA", "TD")]["log_common"] > rows[("TA", "TC")]["log_common"]
    assert rows[("TA", "TD")]["centroid_cos"] > rows[("TA", "TC")]["centroid_cos"]


def test_full_run_produces_the_preregistered_report(world):
    report = backtest.run(max_prior_links=1, min_test_links=3, model="fake")
    assert set(report["models"]) == {"random", "popularity", "network", "semantic", "combined"}
    for m in report["models"].values():
        lo, hi = m["average_precision_ci"]
        assert 0.0 <= lo <= hi <= 1.0
    hyp = report["hypotheses"]
    assert set(hyp) == {"H1_combined_beats_network", "H2_network_beats_popularity",
                        "H3_semantic_beats_popularity"}
    h1 = hyp["H1_combined_beats_network"]
    assert h1["holds"] == (h1["diff_ci"][0] > 0)
    expected = "continue" if h1["holds"] and hyp["H2_network_beats_popularity"]["holds"] else "stop"
    assert report["decision"] == expected
    assert report["pairs"]["eval_positive"] == 1
    assert "Life Sciences / Physical Sciences" in report["by_domain_pair"]


PAIRS = [("TA", "TC"), ("TA", "TD"), ("TB", "TC"), ("TB", "TD"), ("TA", "TE"), ("TB", "TE")]


def test_compare_is_zero_against_itself():
    y = np.array([1, 0, 1, 0, 0, 1])
    s = np.array([0.9, 0.2, 0.8, 0.3, 0.1, 0.7])
    samples = backtest._resamples(y, PAIRS, n=50)
    c = backtest.compare(y, s, s, samples)
    assert c["diff"] == 0.0 and c["diff_ci"] == [0.0, 0.0]


def test_bootstrap_resamples_topics_not_pairs():
    y = np.array([1, 0, 1, 0, 0, 1])
    topics = sorted({t for p in PAIRS for t in p})
    for w in backtest._resamples(y, PAIRS, n=40, seed=3):
        # Each weight is a product of two topic counts that sum to the number of topics.
        assert np.all(w == np.round(w)) and w.min() >= 0
        assert (w * y).sum() > 0 and (w * (1 - y)).sum() > 0
    # The first resample of seed 0 is exactly the product of the topic draws,
    # so a topic that was not drawn takes all of its pairs out of it.
    drawn = np.random.default_rng(0).integers(0, len(topics), len(topics))
    count = dict(zip(topics, np.bincount(drawn, minlength=len(topics))))
    expected = np.array([count[a] * count[b] for a, b in PAIRS], dtype=float)
    assert (expected * y).sum() > 0 and (expected * (1 - y)).sum() > 0
    assert list(backtest._resamples(y, PAIRS, n=1, seed=0)[0]) == list(expected)
    assert any(c == 0 for c in count.values()) and 0.0 in expected


def test_self_citations_do_not_count_as_neighbours(world):
    for p in (world / "topics" / "2017").glob("*.json"):
        rec = json.loads(p.read_text())
        rec["cited_by_train"][rec["topic"]] = 10_000
        p.write_text(json.dumps(rec))
    with_self = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake")
    rows = dict(zip(with_self["pairs"], with_self["rows"]))
    assert rows[("TA", "TD")]["cocite_cosine"] > 0.1


def test_paging_stops_at_a_short_page(monkeypatch):
    calls = []

    def fake_get(path, params):
        calls.append(params["cursor"])
        if params["cursor"] == "*":
            return {"meta": {"next_cursor": "c2"}, "group_by": [{"key": "T1", "count": 1}] * 2}
        return {"meta": {"next_cursor": "c3"}, "group_by": [{"key": "T2", "count": 1}]}

    monkeypatch.setattr(openalex, "get", fake_get)
    pages = list(openalex.paged("works", {"group_by": "primary_topic.id", "per_page": 2}))
    assert calls == ["*", "c2"] and len(pages) == 2


def test_key_is_sent_but_never_cached(monkeypatch, tmp_path):
    sent = []

    class Resp:
        status_code = 200
        headers = {"X-RateLimit-Remaining": "9876"}
        text = "{}"

        def json(self):
            return {"results": []}

    def fake_get(url, params, timeout):
        sent.append(dict(params))
        return Resp()

    monkeypatch.setattr(openalex, "_key", "SECRET")
    monkeypatch.setattr(openalex, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(openalex, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(openalex._session, "get", fake_get)
    openalex.get("works", {"filter": "publication_year:2017"})
    assert sent == [{"filter": "publication_year:2017", "api_key": "SECRET"}]
    assert openalex.remaining == 9876
    keyless = openalex._cache_path("https://api.openalex.org/works?filter=publication_year%3A2017")
    assert keyless.exists()
    files = [f for f in tmp_path.rglob("*") if f.is_file()]
    assert files and not any(b"SECRET" in gzip.decompress(f.read_bytes()) for f in files)


def test_cache_is_compressed_and_reads_old_files(tmp_path, monkeypatch):
    monkeypatch.setattr(openalex, "CACHE_DIR", tmp_path)
    path = openalex._cache_path("https://api.openalex.org/works?x=1")
    path.parent.mkdir(parents=True)
    legacy = path.with_suffix("")                       # an uncompressed file from an older run
    legacy.write_text(json.dumps({"results": [1]}), encoding="utf-8")
    assert openalex._read_cached(path) == {"results": [1]}
    path.write_bytes(gzip.compress(json.dumps({"results": [2]}).encode()))
    assert openalex._read_cached(path) == {"results": [2]}   # the compressed file wins


def test_cleanup_removes_only_what_it_lists(tmp_path, monkeypatch):
    research = tmp_path / "research"
    for rel in ("cache/ab/x.json.gz", "data/topics/2011/T1.json", "data/emb/m/2011.npz",
                "results/r.json", "undiscovered_research/__pycache__/m.pyc", "notes/keep.txt"):
        (research / rel).parent.mkdir(parents=True, exist_ok=True)
        (research / rel).write_text("x")
    hub = tmp_path / "hf" / "hub"
    (hub / "models--BAAI--bge-small-en-v1.5").mkdir(parents=True)
    (hub / "models--other--model").mkdir(parents=True)
    monkeypatch.setattr(cleanup, "RESEARCH", research)
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))

    monkeypatch.setattr("sys.argv", ["cleanup"])
    cleanup.main()
    assert not (research / "cache").exists() and not (research / "data/emb").exists()
    assert not (research / "undiscovered_research/__pycache__").exists()
    assert (research / "data/topics/2011/T1.json").exists() and (research / "results/r.json").exists()
    assert (hub / "models--BAAI--bge-small-en-v1.5").exists()

    monkeypatch.setattr("sys.argv", ["cleanup", "--models", "--data"])
    cleanup.main()
    assert not (research / "data").exists() and not (research / "results").exists()
    assert not (hub / "models--BAAI--bge-small-en-v1.5").exists()
    assert (hub / "models--other--model").exists()          # not ours: untouched
    assert (research / "notes/keep.txt").exists()


def test_robustness_runs_every_planned_variant(world, monkeypatch, tmp_path_factory):
    monkeypatch.setattr(collect, "DATA", world)
    monkeypatch.setattr(embed, "DATA", world)
    result = robustness.run(second_sample=None)
    keys = [v["key"] for v in result["variants"]]
    assert keys == ["main", "k2", "k5", "e0", "bge_small", "bge_base", "seed2027"]
    assert "skipped" in result["variants"][-1]           # reported, not silently dropped
    assert result["main"]["hypotheses"] == result["variants"][0]["hypotheses"]
    e0 = next(v for v in result["variants"] if v["key"] == "e0")
    assert e0["pairs"]["eval"] < result["variants"][0]["pairs"]["eval"]   # TA-TC had one old link

    second = tmp_path_factory.mktemp("second")
    shutil.copytree(world, second, dirs_exist_ok=True)
    result = robustness.run(second_sample=second)
    seed = result["variants"][-1]
    assert "skipped" not in seed and seed["hypotheses"] == result["main"]["hypotheses"]
    assert backtest.DATA == world and embed.DATA == world   # restored afterwards


# Common English words only, so they pass the usable-abstract rule and then
# vanish as stop words or as terms shared by every abstract.
FILLER = ("in this paper we show how it was done and why it is of some use to those who "
          "are in the same place as we are and what we would do if we had to do it again")


def english(keywords: str) -> str:
    return f"{FILLER} {keywords}"


def test_usable_abstracts_are_english_and_long_enough():
    assert embed.usable(english("kalman filter state estimation"))
    assert not embed.usable("Towards a risk assessment of Trichinella. International audience")
    assert not embed.usable("水稻的生长 " * 60)
    french = ("Ce texte est disponible en format PDF seulement et les auteurs ont choisi de "
              "ne pas le publier ici car la revue ne le permet pas pour des raisons de droits "
              "qui sont propres a chaque editeur et a chaque pays ou la recherche est faite")
    assert not embed.usable(french)
    topics = {"TA": [{"text": english("alpha")}] * 5, "TB": [{"text": english("beta")}] * 4}
    assert set(embed.usable_abstracts(topics)) == {"TA"}       # TB has too few


def test_tfidf_vectors_use_only_the_given_abstracts():
    words = {"TA": "kalman filter noisy sensor estimation", "TB": "assimilation weather noisy sensor estimation",
             "TC": "poetry translation medieval manuscripts", "TD": "glacier ice core isotopes",
             "TE": "tax policy household income"}
    abstracts = {t: [{"text": english(w)}] * 5 for t, w in words.items()}
    emb = embed.topic_embeddings(2017, embed.TFIDF, abstracts)
    assert set(emb) == set(words)
    cos = lambda a, b: float(emb[a]["centroid"] @ emb[b]["centroid"])
    assert cos("TA", "TB") > 0.3 and cos("TA", "TC") == 0.0
    assert abs(cos("TA", "TA") - 1.0) < 1e-5


def test_pair_table_runs_on_tfidf_vectors(world, monkeypatch):
    # Words shared by more than half the abstracts are dropped (max_df), so
    # TB and TD share two words that no other topic uses, and TA and TC none.
    texts = {"TA": "proline assay leaf tissue", "TB": "drought sensor root growth",
             "TC": "named content caching routers", "TD": "drought sensor packet delivery"}
    for cutoff in collect.CUTOFFS:
        for p in (world / "topics" / str(cutoff)).glob("*.json"):
            rec = json.loads(p.read_text())
            rec["abstracts"] = [{"id": f"W{n}", "text": english(texts[rec["topic"]])} for n in range(5)]
            p.write_text(json.dumps(rec))
    monkeypatch.setattr(backtest, "topic_embeddings", embed.topic_embeddings)
    table = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model=embed.TFIDF)
    rows = dict(zip(table["pairs"], table["rows"]))
    assert rows[("TA", "TC")]["centroid_cos"] == 0.0 and rows[("TA", "TC")]["top_pairs_cos"] == 0.0
    assert rows[("TB", "TD")]["centroid_cos"] > 0.3
