"""Offline tests: no network, no model download."""

from __future__ import annotations

import gzip
import json
import shutil

import numpy as np
import pytest

from undiscovered_research import backtest, cleanup, collect, embed, openalex, robustness, strict

# Common English words only, so they pass the usable-abstract rule and then
# vanish as stop words or as terms shared by every abstract.
FILLER = ("in this paper we show how it was done and why it is of some use to those who "
          "are in the same place as we are and what we would do if we had to do it again")


def english(keywords: str) -> str:
    return f"{FILLER} {keywords}"


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


def test_reference_papers_count_only_citations_up_to_the_cutoff(monkeypatch):
    # W2 is the most cited today, but almost all of it came after 2017.
    works = [
        {"id": "https://openalex.org/W2", "cited_by_count": 900,
         "counts_by_year": [{"year": 2019, "cited_by_count": 600}, {"year": 2018, "cited_by_count": 290}]},
        {"id": "https://openalex.org/W1", "cited_by_count": 300,
         "counts_by_year": [{"year": 2016, "cited_by_count": 50}, {"year": 2019, "cited_by_count": 20}]},
        {"id": "https://openalex.org/W3", "cited_by_count": 5,
         "counts_by_year": [{"year": 2020, "cited_by_count": 5}]},     # nothing before 2018
    ]
    assert collect.citations_up_to(works[0], 2017) == 10
    assert collect.citations_up_to(works[1], 2017) == 280
    monkeypatch.setattr(collect.oa, "paged", lambda path, params: iter([{"results": works}]))
    assert collect.reference_papers("T1", 2017) == ["W1", "W2"]          # W3 had no citations yet


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Six topics in two domains.

    A-D and E-F connect after the cutoff; A-C stay apart with one old link;
    B-C were linked long before the train window, so they are not
    "unconnected". X is a topic outside the sample.
    """
    topics = [
        {"id": "TA", "name": "a", "domain": "Life Sciences", "subfield": "sa"},
        {"id": "TB", "name": "b", "domain": "Life Sciences", "subfield": "sb"},
        {"id": "TE", "name": "e", "domain": "Life Sciences", "subfield": "se"},
        {"id": "TC", "name": "c", "domain": "Physical Sciences", "subfield": "sc"},
        {"id": "TD", "name": "d", "domain": "Physical Sciences", "subfield": "sd"},
        {"id": "TF", "name": "f", "domain": "Physical Sciences", "subfield": "sf"},
    ]
    (tmp_path / "sample.json").write_text(json.dumps(topics))
    citing = {  # topic -> (cited_by_before, cited_by_train, cited_by_recent, cited_by_test)
        "TA": ({"TC": 1}, {"TB": 9, "TX": 4}, {"TB": 3}, {"TB": 9, "TD": 5}),
        "TB": ({}, {"TA": 7, "TX": 2, "TD": 1}, {"TA": 2}, {"TA": 6}),
        "TC": ({"TB": 4}, {"TD": 3}, {"TD": 1}, {"TD": 3}),
        "TD": ({}, {"TC": 2, "TX": 1}, {"TX": 1}, {"TC": 2}),
        "TE": ({}, {"TX": 3}, {"TX": 2}, {"TF": 2}),
        "TF": ({}, {"TX": 2}, {}, {"TE": 2}),
    }
    for cutoff in collect.CUTOFFS:
        d = tmp_path / "topics" / str(cutoff)
        d.mkdir(parents=True)
        train = (cutoff - collect.TRAIN_YEARS, cutoff)
        for tid, (before, tr, rec_, te) in citing.items():
            d.joinpath(f"{tid}.json").write_text(json.dumps({
                "format": collect.FORMAT, "topic": tid, "cutoff": cutoff,
                "train_window": train, "test_window": (cutoff + 1, cutoff + collect.TEST_YEARS),
                "recent_window": (cutoff - 2, cutoff),
                "size": 800, "works_by_year": {str(y): 100 for y in range(train[0], train[1] + 1)},
                "instrument": ["W1"],
                "abstracts": [{"id": f"W{n}", "text": english(f"topic {tid.lower()}")} for n in range(5)],
                "cited_by_before": before, "cited_by_train": tr, "cited_by_recent": rec_,
                "cited_by_test": te,
            }))
    monkeypatch.setattr(backtest, "DATA", tmp_path)
    vec = {"TA": [1.0, 0.0], "TB": [0.9, 0.1], "TE": [0.6, 0.8],
           "TC": [0.0, 1.0], "TD": [0.7, 0.7], "TF": [0.5, 0.9]}

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
    assert ("TB", "TD") in pairs                         # exactly one earlier link: still unconnected
    label = dict(zip(table["pairs"], table["labels"]))
    assert label[("TA", "TD")] == 1                      # 5 citing works after the cutoff
    assert label[("TA", "TC")] == 0 and label[("TE", "TF")] == 1
    links = dict(zip(table["pairs"], table["links"]))
    assert links[("TA", "TC")] == (1, 0)                 # one old link is still "unconnected"
    directions = dict(zip(table["pairs"], table["directions"]))
    assert directions[("TA", "TD")] == (0, 5)            # works in TD citing TA's papers


def test_load_refuses_an_incomplete_or_old_sample(world):
    (world / "topics" / "2017" / "TF.json").unlink()
    with pytest.raises(SystemExit, match="missing or in an old format"):
        backtest.load(2017)
    rec = json.loads((world / "topics" / "2011" / "TA.json").read_text())
    rec["format"] = 1
    (world / "topics" / "2011" / "TA.json").write_text(json.dumps(rec))
    with pytest.raises(SystemExit):
        backtest.load(2011)


def test_pair_table_features(world):
    table = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake")
    rows = dict(zip(table["pairs"], table["rows"]))
    # TA and TD are both cited by TX; TA and TC share no citing topic.
    assert rows[("TA", "TD")]["log_common"] > rows[("TA", "TC")]["log_common"]
    assert rows[("TA", "TD")]["centroid_cos"] > rows[("TA", "TC")]["centroid_cos"]
    # TA cites TB (TA is among TB's citers) and TB cites TD: a two-step path A -> B -> D.
    assert rows[("TA", "TD")]["log_two_hop"] > 0
    assert rows[("TA", "TC")]["prior_links"] == 1.0 and rows[("TA", "TD")]["prior_links"] == 0.0
    assert rows[("TA", "TD")]["growth_hi"] == 0.0         # flat output in every year
    # Only one pair of domains here, so every pair has the same indicators.
    assert {tuple(r[f] for f in backtest.DP_FEATURES) for r in table["rows"]} == {
        tuple(float(p == "Life Sciences / Physical Sciences") for p in backtest.DOMAIN_PAIRS[1:])}
    assert set(backtest.FEATURE_SETS["combined"]) <= set(table["rows"][0])


def test_self_citations_do_not_count_as_neighbours(world):
    for p in (world / "topics" / "2017").glob("*.json"):
        rec = json.loads(p.read_text())
        rec["cited_by_train"][rec["topic"]] = 10_000
        p.write_text(json.dumps(rec))
    rows = dict(zip(*(lambda t: (t["pairs"], t["rows"]))(
        backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake"))))
    assert rows[("TA", "TD")]["cocite_cosine"] > 0.1


def test_h1_has_three_outcomes():
    assert backtest.h1_outcome([0.001, 0.02], network_ap=0.1) == "supported"
    assert backtest.h1_outcome([-0.02, 0.005], network_ap=0.1) == "negative"     # rules out a 10% gain
    assert backtest.h1_outcome([-0.02, 0.03], network_ap=0.1) == "inconclusive"


def test_bootstrap_draws_topics_within_each_domain():
    rng = np.random.default_rng(0)
    by_domain = {"Life Sciences": ["TA", "TB", "TE"], "Physical Sciences": ["TC", "TD"]}
    for _ in range(20):
        count = backtest.topic_draws(by_domain, rng)
        assert sum(count[t] for t in by_domain["Life Sciences"]) == 3
        assert sum(count[t] for t in by_domain["Physical Sciences"]) == 2
    w = backtest.pair_weights([("TA", "TC"), ("TB", "TD")], {"TA": 2, "TC": 3, "TB": 0, "TD": 1})
    assert list(w) == [6.0, 0.0]                          # a topic not drawn removes its pairs


def test_full_run_produces_the_preregistered_report(world):
    strict_links = {("TA", "TD"): 4, ("TE", "TF"): 0}
    report = backtest.run(max_prior_links=1, min_test_links=3, model="fake", n_boot=20,
                          strict_links=strict_links)
    assert set(report["models"]) == {"random", "popularity", "network", "semantic", "combined"}
    for m in report["models"].values():
        lo, hi = m["average_precision_ci"]
        assert 0.0 <= lo <= hi <= 1.0
    hyp = report["hypotheses"]
    h1 = hyp["H1_combined_beats_network"]
    assert h1["outcome"] in {"supported", "negative", "inconclusive"}
    assert h1["holds"] == (h1["outcome"] == "supported")
    assert report["strict"]["positive"] == 1
    expected = ("continue" if h1["holds"] and hyp["H2_network_beats_popularity"]["holds"]
                and report["strict"]["holds"] else "stop")
    assert report["decision"] == expected
    assert report["pairs"]["eval_positive"] == 2
    assert report["directions"] == {"both": 1, "one_way": 1}     # E-F both ways, A-D one way
    assert "Life Sciences / Physical Sciences" in report["by_domain_pair"]
    assert set(report["feature_shift"]) == set(backtest.FEATURE_SETS["combined"])
    # Without the strict label the run cannot decide.
    assert backtest.run(1, 3, "fake", n_boot=5)["decision"] == "incomplete"


def test_strict_label_drops_works_filed_near_the_other_topic(world, monkeypatch):
    ev = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model="fake")
    seen = []

    def fake_paged(path, params):
        seen.append(params["filter"])
        # Works in TD citing TA's papers; "sa" is TA's subfield.
        yield {"results": [
            {"id": "W10", "topics": [{"subfield": {"display_name": "sd"}}]},
            {"id": "W11", "topics": [{"subfield": {"display_name": "sd"}},
                                     {"subfield": {"display_name": "sa"}}]},    # also filed near TA
            {"id": "W12", "topics": []},
        ]}

    monkeypatch.setattr(strict.oa, "paged", fake_paged)
    counts = strict.collect(ev, min_test_links=3)
    assert counts[("TA", "TD")] == 2                     # W11 is left out
    assert ("TA", "TC") not in counts                    # did not connect: never fetched
    assert all("type:article|review" in f and "publication_year:2018-2023" in f for f in seen)


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
    main = backtest.run(1, 3, "fake", n_boot=10, strict_links={("TA", "TD"): 4})
    result = robustness.run(main, second_sample=None, n_boot=10)
    keys = [v["key"] for v in result["variants"]]
    assert keys == ["main", "strict", "k2", "k5", "e0", "large", "bge_small", "bge_base", "seed2027"]
    assert "skipped" in result["variants"][-1]           # reported, not silently dropped
    e0 = next(v for v in result["variants"] if v["key"] == "e0")
    assert e0["pairs"]["eval"] < main["pairs"]["eval"]   # TA-TC had one old link
    large = next(v for v in result["variants"] if v["key"] == "large")
    assert large["pairs"]["eval"] == main["pairs"]["eval"]   # every topic has 800 works

    second = tmp_path_factory.mktemp("second")
    shutil.copytree(world, second, dirs_exist_ok=True)
    result = robustness.run(main, second_sample=second, n_boot=10)
    seed = result["variants"][-1]
    assert "skipped" not in seed
    assert seed["hypotheses"]["H1_combined_beats_network"]["diff"] == \
        main["hypotheses"]["H1_combined_beats_network"]["diff"]
    assert backtest.DATA == world and embed.DATA == world   # restored afterwards


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


def test_cleaning_and_stop_words():
    text = ("Background: we grew thin films. RESULTS: they stay thin. (c) 2015 Elsevier Ltd. "
            "All rights reserved. The background radiation was low.")
    cleaned = embed.clean(text)
    assert "Background:" not in cleaned and "RESULTS:" not in cleaned
    assert "rights reserved" not in cleaned and "background radiation" in cleaned
    stops = embed.stop_words()
    assert {"thin", "system", "fire", "interest"}.isdisjoint(stops)      # words with meaning
    assert {"the", "and", "elsevier", "copyright"} <= stops


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
             "TC": "named content caching routers", "TD": "drought sensor packet delivery",
             "TE": "glacier ice core isotopes", "TF": "tax policy household income"}
    for cutoff in collect.CUTOFFS:
        for p in (world / "topics" / str(cutoff)).glob("*.json"):
            rec = json.loads(p.read_text())
            rec["abstracts"] = [{"id": f"W{n}", "text": english(texts[rec["topic"]])} for n in range(5)]
            p.write_text(json.dumps(rec))
    monkeypatch.setattr(backtest, "topic_embeddings", embed.topic_embeddings)
    table = backtest.pair_table(2017, max_prior_links=1, min_test_links=3, model=embed.TFIDF)
    rows = dict(zip(table["pairs"], table["rows"]))
    assert rows[("TA", "TC")]["centroid_cos"] == 0.0 and rows[("TA", "TC")]["top_pairs_cos"] == 0.0
    assert rows[("TA", "TD")]["log_usable_lo"] == pytest.approx(np.log(5))


def test_a_variant_without_enough_data_is_reported_not_fatal(world, monkeypatch):
    monkeypatch.setattr(collect, "DATA", world)
    monkeypatch.setattr(embed, "DATA", world)
    with pytest.raises(backtest.NotEnoughData, match="no positive fitting pairs"):
        backtest.run(1, 50, "fake", n_boot=5)                  # nobody reaches 50 links
    main = backtest.run(1, 3, "fake", n_boot=5, strict_links={("TA", "TD"): 4})
    monkeypatch.setattr(robustness, "VARIANTS", [("big", "Huge topics only", {"min_size": 10**6})])
    result = robustness.run(main, second_sample=None, n_boot=5)
    assert result["variants"][-1]["skipped"] == "no fitting pairs under these settings"
