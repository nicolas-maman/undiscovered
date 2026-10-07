# Analysis plan for the first backtest

This plan was written and committed before any model was fitted and before
any label was computed. Git history records when. Anything decided after the
results are seen will be listed under *Deviations* at the end and reported
as exploratory.

What had been done when this was written: the data pipeline was tested on a
pilot of 40 topics (cutoff 2012 only), to check that the OpenAlex queries
return what the design needs. Counts of citing topics per topic were looked
at to check the pipeline; no pair was labelled and nothing was modelled. That
pilot used an earlier version of the pipeline and is not part of the
analysis.

## Question

Two research topics from different domains (physical, life, health or social
sciences) that have barely cited each other: can we predict whether they
start citing each other within the next six years?

The specific question is whether **what the two topics' papers say** adds
predictive power to **the shape of the citation network around them**. The
network features are the published method to beat (Science4Cast, Krenn et
al., *Nature Machine Intelligence*, 2023, found that carefully chosen network
features beat end-to-end models on a related task).

## Hypotheses

- **H1 (primary).** The `combined` model has a higher average precision than
  the `network` model on the 2017 evaluation, and the 95% bootstrap interval
  of the difference lies above zero.
- **H2 (sanity check).** The `network` model has a higher average precision
  than the `popularity` model. If it does not, the reproduction of the
  published method failed, and H1 is not interpreted.
- **H3 (secondary).** The `semantic` model has a higher average precision than
  the `popularity` model.

## Data

- **Source:** OpenAlex, accessed in October 2026, through the cached client in
  `undiscovered_research/openalex.py`.
- **Topics:** 75 per domain, 300 in total, drawn with seed 2026 from the 4,516
  OpenAlex topics (`collect.sample_topics`).
- **Topic of a work:** its OpenAlex primary topic.
- **Cutoffs:** 2012 (train window 2005 to 2012, test window 2013 to 2018) is
  used only to fit the models. 2017 (train window 2010 to 2017, test window
  2018 to 2023) is used only to evaluate them.
- **Instrument:** for each topic and cutoff, its 100 most-cited works
  published up to the cutoff.
- **Link from A to B in a window:** works whose primary topic is A, published
  in the window, that cite at least one of B's instrument works. A pair's
  link count is the sum of both directions.
- **Abstracts:** 40 works per topic and cutoff, drawn at random (OpenAlex
  `sample`, seed 17) from the topic's works in the train window that have an
  abstract.
- **Embedding model:** `BAAI/bge-small-en-v1.5`, chosen in advance because it
  is small, open and runs on a CPU.

## Units and labels

- A unit is an unordered pair of sampled topics from different domains.
- A pair is **eligible** if it has at most 1 link in all the years up to
  the cutoff (see the amendment of 2026-10-07 below).
- An eligible pair is **positive** if its test-window link count is at least 3.

## Models

Logistic regression with balanced class weights on standardised features,
fitted on the 2012 cutoff and applied unchanged to the 2017 cutoff. The
feature sets are exactly those in `undiscovered_research/backtest.py` as of the
commit that adds this file:

- `popularity`: log size of the larger and of the smaller topic.
- `network`: popularity, plus the two topics' degrees, the log number of
  topics citing both, their Jaccard index, Adamic-Adar, and the cosine of
  their citing-topic count vectors.
- `semantic`: popularity, plus the cosine of the two topics' abstract
  centroids and the mean of the five highest cosines between their
  individual abstracts.
- `combined`: the union of the above.

A random score is reported as a floor.

## Metrics

- **Primary:** average precision on the 2017 evaluation pairs.
- **Secondary:** ROC-AUC, precision at 100 and at 1,000, and the base rate.
- **Uncertainty:** 300 bootstrap resamples of the evaluation pairs, with a
  95% percentile interval for each model's average precision and for the
  difference between models.

## Decision

- **Continue** to the distributed parts of the project (clients, work units,
  aggregation) if H1 holds and H2 holds.
- **Stop and publish a negative result** if H1 does not hold. Features will
  not be tuned on the 2017 evaluation to rescue it. A redesigned method would
  need a new cutoff that has not been looked at.
- **In every case,** all numbers in this plan are published in the README and
  on the site, together with the code and the commit used.

## Robustness checks

These are reported alongside the main result and do not change the decision:

1. Positive threshold of 2 and of 5 test-window links, instead of 3.
2. Eligibility of 0 links up to the cutoff, instead of at most 1.
3. A second embedding model: `BAAI/bge-base-en-v1.5`.
4. A second sample of 300 topics, drawn with seed 2027.
5. Results by domain pair (for example life sciences with physical sciences).

## Known limitations

- OpenAlex assigns topics to works of every year with one present-day
  classifier. This affects features and labels alike.
- The instrument is chosen by all-time citation counts, which include
  citations made after the cutoff. Only the labels use the test window; no
  feature does.
- A citation is a proxy for one field using another's work. It misses use
  without citation and counts citation without real use.
- 300 of 4,516 topics are sampled, so neighbourhoods are complete, but the
  set of candidate pairs is a sample.

## Amendments before data collection

- **2026-10-07, eligibility.** The first version counted links only in the
  train window (seven years), so a pair of topics that cited each other
  heavily before 2010 but rarely in 2010 to 2017 would have counted as
  "unconnected", and its return would have been an easy prediction rather
  than a discovery. Eligibility now counts links in every year up to the
  cutoff, which is what Science4Cast means by "not yet connected". The
  collector fetches the earlier years for the sampled topics only, about
  1,800 extra requests. This was decided before any analysis data was
  collected and before any model was fitted. The only data fetched so far
  is a pilot that tested the queries (42 topics at the 2012 cutoff and 3 at
  2017, with an earlier query design), which is not used in the analysis.

## Deviations

None yet. Any change made after results are seen will be listed here with
its date and reason.
