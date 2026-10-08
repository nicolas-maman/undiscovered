# The backtest

Can we predict which distant fields will start citing each other?

## Design

- **Unit:** a pair of OpenAlex topics from different domains (physical, life,
  health, social sciences) that were connected by at most one citing work in
  all the years up to the cutoff.
- **Topics:** OpenAlex *primary* topics, so each work counts once, under the
  topic it is most about.
- **Link:** works whose primary topic is A, published in a window, that cite
  one of topic B's 100 most-cited papers published up to the cutoff (or the
  reverse). OpenAlex counts that for every citing topic in one grouped
  request. The train window is fetched in full, because the network features
  need each topic's whole neighbourhood. The test window, and the years
  before the train window (used only to decide which pairs were never
  connected), are fetched only for the sampled topics, in chunks of 100,
  because they only concern sampled pairs. A 300-topic run takes about
  7,200 requests (measured: about 12 per topic and cutoff), which fits in
  one day with a free key, or about a week without one.
- **Label:** the pair has at least 3 links in the test window.
- **Windows:** cutoff 2011 (train 2004 to 2011, test 2012 to 2017) fits the
  models; cutoff 2017 (train 2010 to 2017, test 2018 to 2023) is the evaluation.
  Every reported number is out of time.
- **Models:** logistic regression on
  - `popularity`: the two topics' sizes;
  - `network`: Science4Cast-style structure of the citation graph: common
    citing topics, Jaccard, Adamic-Adar, co-citation cosine and degrees. This
    is the kind of model that did best in Science4Cast, and the baseline
    to beat;
  - `semantic`: content similarity of each topic's sampled pre-cutoff
    abstracts, with TF-IDF fitted at each cutoff on that cutoff's abstracts
    only. A pretrained embedding model could have been trained on papers
    and citations from after the cutoff; pretrained models are used only in
    a robustness check;
  - `combined`.
- **Metrics:** ROC-AUC, average precision, precision@100 and @1000, and a
  bootstrap 95% interval on the difference with `network`. The bootstrap
  resamples topics, not pairs, because pairs that share a topic are not
  independent.

### Guarding against the future leaking in

- The abstracts that describe a topic are a **random** sample of its
  pre-cutoff papers (OpenAlex `sample` with a fixed seed), not its most cited:
  all-time citation counts include citations made after the cutoff. Only
  English texts of at least 40 words count, so placeholders and shared
  languages cannot make two topics look alike.
- No feature uses topic descriptions or keywords; those were written from the
  whole corpus.
- The models are fitted only at the 2011 freeze, whose outcomes end in 2017.
  Nothing from 2018 on is used to fit anything.
- Known residual: OpenAlex assigns topics with one present-day classifier for
  every year, which affects labels and features alike.
- Known residual: the 100 papers that stand for each topic are its most cited
  by today's counts, which include citations made after the cutoff. This
  decides which papers count as the topic, for every model alike; no feature
  counts a citation made after the cutoff.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r research/requirements.txt
cd research
python -m undiscovered_research.collect    # OpenAlex; cached, stops and resumes
python -m undiscovered_research.backtest   # writes results/backtest_e1_k3_tfidf.json
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

The robustness checks also use pretrained embeddings, from a local open
model by default (free, no account). To use any OpenAI-compatible
embeddings endpoint instead (Ollama, LM Studio, vLLM or a hosted provider),
set `UNDISCOVERED_EMBED_URL` (and `UNDISCOVERED_EMBED_KEY` if it needs one)
and pass `--model`.

## What comes next

A draft, written before the first result: [NEXT.md](NEXT.md).
