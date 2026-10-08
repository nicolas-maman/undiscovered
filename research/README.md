# The backtest

Can we predict which distant fields will start citing each other?

## Design

The full plan, with every threshold and the reason for each change, is in
[PREREGISTRATION.md](PREREGISTRATION.md). In short:

- Unit: a pair of OpenAlex topics from different domains (physical, life,
  health, social sciences) that were connected by at most one citing work
  in all the years up to the cutoff.
- Topics: OpenAlex primary topics, so each work counts once, under the
  topic it is most about.
- Reference papers: for each topic, its 100 papers published up to the
  cutoff with the most citations received up to the cutoff (today's
  counts minus later years). Today's counts alone would pick papers for
  citations they only received later.
- Link: works whose primary topic is A, published in a window, that cite
  one of topic B's reference papers (or the reverse). OpenAlex counts that
  for every citing topic in one grouped request. The train window and its
  last three years are fetched in full, because the network features need
  each topic's whole neighbourhood. The test window, and the years before
  the train window (used only to decide which pairs were never connected),
  are fetched only for the sampled topics.
- Label: the pair has at least 3 links in the test window. A stricter
  version, counting only articles and reviews that OpenAlex does not also
  file near the other topic, guards against misfiled papers.
- Windows: cutoff 2011 (train 2004 to 2011, test 2012 to 2017) fits the
  models; cutoff 2017 (train 2010 to 2017, test 2018 to 2023) is the
  evaluation. Every reported number comes from years the model never saw
  when it was fitted.
- Models, all logistic regression:
  - `popularity`: the two topics' sizes and growth, how many usable
    abstracts each has, and which pair of domains they come from. Every
    other model includes these;
  - `network`: the citation network around the pair, now and in the last
    three years: degrees, common citing topics, Jaccard, Adamic-Adar,
    co-citation cosine, two-step paths and any earlier link. These are the
    kinds of features that did best in Science4Cast, and the baseline to
    beat;
  - `semantic`: how close the two topics' abstracts are, with TF-IDF fitted
    at each cutoff on that cutoff's abstracts only. A pretrained embedding
    model could have been trained on papers and citations from after the
    cutoff, so pretrained models are used only in a robustness check;
  - `combined`.
- Metrics: average precision (primary), ROC-AUC, precision at 100 and at
  1,000, with 95% intervals from 2,000 bootstrap replicates that resample
  topics within each domain and refit every model each time.
- Cost: about 16 OpenAlex requests per topic and cutoff, so about 9,600 per
  300-topic sample, plus a few per connected pair for the stricter label.
  With a free key that is about a day per sample.

### Guarding against the future leaking in

- Reference papers are chosen by citations made up to the cutoff.
- The abstracts that describe a topic are a random sample of its pre-cutoff
  papers (OpenAlex `sample` with a fixed seed), not its most cited. Only
  English texts of at least 40 words count, so placeholder text and a
  shared non-English language are much less likely to make two topics look
  alike.
- No feature uses topic descriptions or keywords; those were written from
  the whole corpus.
- The models are fitted only at the 2011 freeze, whose outcomes end in 2017.
- Known residual: OpenAlex files works under topics with one present-day
  classifier, a language model trained on recent text, for every year. The
  plan's robustness check on long-established topics and the stricter
  label address it.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r research/requirements.txt   # or requirements-lock.txt for the exact versions used
cd research
python -m undiscovered_research.collect    # OpenAlex; cached, stops and resumes
python -m undiscovered_research.backtest   # fetches the stricter label, writes results/backtest_e1_k3_tfidf.json
pytest                                     # offline tests
```

The robustness checks listed in the plan need a second topic sample, then
one command runs them all; `publish` copies the result to the site with the
commit it came from:

```bash
python -m undiscovered_research.collect --seed 2027 --data data_seed2027
python -m undiscovered_research.robustness           # writes results/robustness.json
python -m undiscovered_research.publish results/backtest_e1_k3_tfidf.json --robustness results/robustness.json
```

OpenAlex is free. A free key from <https://openalex.org/settings/api>
(`OPENALEX_API_KEY`, or a `research/.openalex_key` file) gives about 10,000
queries a day; without one the shared budget is about a tenth of that. The
collector stops cleanly when the day's budget is spent and resumes where it
left off.

The robustness checks also use pretrained embeddings. They need extra
packages, which are large (PyTorch alone is over 500 MB), so they are kept
apart: see `research/requirements-embeddings.txt`. The model runs locally
by default (free, no account). To use any OpenAI-compatible embeddings
endpoint instead (Ollama, LM Studio, vLLM or a hosted provider), set
`UNDISCOVERED_EMBED_URL` (and `UNDISCOVERED_EMBED_KEY` if it needs one)
and run `backtest` with `--model <name>`; the robustness command always uses
the two BGE models named in the plan.

### What it does to your computer

- Every command runs at low priority and uses at most half of the CPU
  cores, so whatever else you are doing comes first.
- The collector mostly waits on the network: in our runs it used a few
  seconds of CPU per ten minutes and about 40 MB of memory.
- On disk: the collected data takes about 40 MB per topic sample. While a
  collection runs, OpenAlex's answers are kept, compressed, in
  `research/cache/` so an interrupted run can resume without spending its
  budget twice; the collector deletes that cache when the sample is
  complete.
- To remove everything that can be rebuilt, at any time except during a
  collection:

```bash
python -m undiscovered_research.cleanup            # caches
python -m undiscovered_research.cleanup --models   # and downloaded embedding models
python -m undiscovered_research.cleanup --data     # and the collected data and results
```

## What comes next

A draft, written before the first result: [NEXT.md](NEXT.md).
