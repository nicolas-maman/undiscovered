# The backtest

Can we predict which distant fields will start citing each other?

## Design

- **Unit:** a pair of OpenAlex topics from different domains (physical, life,
  health, social sciences) that were connected by at most one citing work in
  the train window.
- **Link:** works in topic A, published in a window, that cite one of topic
  B's 100 most-cited papers published up to the cutoff (or the reverse).
  OpenAlex counts that for every citing topic in one grouped request.
- **Label:** the pair has at least 3 links in the test window.
- **Windows:** cutoff 2012 (train 2005–2012, test 2013–2018) fits the
  models; cutoff 2017 (train 2010–2017, test 2018–2023) is the evaluation.
  Every reported number is out of time.
- **Models:** logistic regression on
  - `popularity`: the two topics' sizes;
  - `network`: Science4Cast-style structure of the citation graph — common
    citing topics, Jaccard, Adamic–Adar, co-citation cosine, degrees (the
    prior art to beat);
  - `semantic`: embedding similarity of each topic's sampled pre-cutoff
    abstracts;
  - `combined`.
- **Metrics:** ROC-AUC, average precision, precision@100 and @1000, and a
  bootstrap 95% interval on the difference with `network`.

### Guarding against the future leaking in

- The abstracts that describe a topic are a **random** sample of its
  pre-cutoff papers (OpenAlex `sample` with a fixed seed), not its most cited:
  all-time citation counts include citations made after the cutoff.
- No feature uses topic descriptions or keywords; those were written from the
  whole corpus.
- Known residual: OpenAlex assigns topics with one present-day classifier for
  every year, which affects labels and features alike.

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r research/requirements.txt
cd research
python -m undiscovered_research.collect --per-domain 75   # OpenAlex; cached
python -m undiscovered_research.backtest                  # prints and writes results/
```

OpenAlex is free. A free key from <https://openalex.org/settings/api>
(`OPENALEX_API_KEY`, or a `research/.openalex_key` file) gives about 10,000
queries a day; without one the shared budget is about a tenth of that. The
collector stops cleanly when the day's budget is spent and resumes where it
left off.

Embeddings default to a local open model (`BAAI/bge-small-en-v1.5`, free, no
account). To use any OpenAI-compatible embeddings endpoint instead — Ollama,
LM Studio, vLLM, or a hosted provider — set `UNDISCOVERED_EMBED_URL` (and
`UNDISCOVERED_EMBED_KEY` if it needs one) and pass `--model`.
