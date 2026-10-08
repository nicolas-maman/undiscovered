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
- **Cutoffs:** 2011 (train window 2004 to 2011, test window 2012 to 2017) is
  used only to fit the models (amended 2026-10-07, see below). 2017 (train window 2010 to 2017, test window
  2018 to 2023) is used only to evaluate them.
- **Instrument:** for each topic and cutoff, its 100 most-cited works
  published up to the cutoff.
- **Link from A to B in a window:** works whose primary topic is A, published
  in the window, that cite at least one of B's instrument works. A pair's
  link count is the sum of both directions.
- **Abstracts:** 40 works per topic and cutoff, drawn at random (OpenAlex
  `sample`, seed 17) from the topic's works in the train window that have an
  abstract. Only usable ones count: title and abstract together have at
  least 40 words, and at least a quarter of them are common English words
  (scikit-learn's English stop-word list). A topic with fewer than 5 usable
  abstracts has no content vector, and its pairs are left out for every
  model. (Amended 2026-10-08.)
- **Content vectors:** TF-IDF fitted, at each cutoff, on that cutoff's
  sampled abstracts and nothing else: English stop words removed, sublinear
  term frequency, terms that appear in at least 2 and at most half of the
  abstracts, single words. (Amended 2026-10-08; the first version used the
  pretrained model `BAAI/bge-small-en-v1.5`, see below.)

## Units and labels

- A unit is an unordered pair of sampled topics from different domains.
- A pair is **eligible** if it has at most 1 link in all the years up to
  the cutoff (see the amendment of 2026-10-07 below).
- An eligible pair is **positive** if its test-window link count is at least 3.

## Models

Logistic regression with balanced class weights on standardised features,
fitted on the 2011 cutoff and applied unchanged to the 2017 cutoff. The
feature sets are exactly those in `undiscovered_research/backtest.py` as of the
commit that adds this file:

- `popularity`: log size of the larger and of the smaller topic.
- `network`: popularity, plus the two topics' degrees, the log number of
  topics citing both, their Jaccard index, Adamic-Adar, and the cosine of
  their citing-topic count vectors. A topic's citations of itself are not
  part of its neighbourhood (amended 2026-10-07).
- `semantic`: popularity, plus the cosine of the two topics' abstract
  centroids and the mean of the five highest cosines between their
  individual abstracts.
- `combined`: the union of the above.

A random score is reported as a floor.

## Metrics

- **Primary:** average precision on the 2017 evaluation pairs.
- **Secondary:** ROC-AUC, precision at 100 and at 1,000, and the base rate.
- **Uncertainty:** 300 bootstrap resamples of the evaluation *topics*
  (amended 2026-10-07): topics are drawn with replacement and each pair is
  weighted by how many times each of its two topics was drawn. The same
  resamples serve every model. 95% percentile intervals are reported for
  each model's average precision and for the difference between models.

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
3. Pretrained embeddings instead of TF-IDF: `BAAI/bge-small-en-v1.5` and
   `BAAI/bge-base-en-v1.5` (amended 2026-10-08).
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
- The pretrained embedding models in robustness check 3 may have been
  trained on literature from after the cutoff. The main analysis does not
  use them.

## Amendments before analysis

- **2026-10-07, eligibility.** The first version counted links only in the
  train window (seven years), so a pair of topics that cited each other
  heavily before 2010 but rarely in 2010 to 2017 would have counted as
  "unconnected", and its return would have been an easy prediction rather
  than a discovery. Eligibility now counts links in every year up to the
  cutoff, as Science4Cast does when it asks which pairs are still
  unconnected (we still allow one stray citing work). The
  collector fetches the earlier years for the sampled topics only, about
  1,800 extra requests. This was decided before any analysis data was
  collected and before any model was fitted. The only data fetched so far
  is the pilot described at the top, with an earlier query design, which is
  not used in the analysis. (Correction: besides the 40 topics at 2012, the
  pilot had also fetched 3 topics at 2017.)
- **2026-10-07, fitting cutoff 2011 instead of 2012.** With 2012, the
  fitting labels came from 2013 to 2018, which shares the year 2018 with the
  evaluation window. With 2011 they come from 2012 to 2017, so nothing after
  2017 is used to fit anything, and "frozen at the end of 2017" holds for
  the whole pipeline. Same reason for timing as above: decided before any
  analysis data was collected.
- **2026-10-07, bootstrap over topics instead of pairs.** Pairs that share
  a topic are not independent: if a model misjudges one topic, it misjudges
  all of that topic's pairs together. Resampling pairs would treat tens of
  thousands of dependent pairs as independent and give intervals that are
  too narrow, which would make H1 easier to pass by chance. Resampling
  topics keeps that dependence. It is expected to widen the intervals, so
  it makes H1 harder to pass, not easier.
- **2026-10-07, self-citations out of the neighbourhood.** A topic's
  citations of its own most-cited papers were counted among its citing
  topics. In the pilot they were among a topic's three largest counts for
  34 of 40 topics, so they would have weighed heavily on the co-citation
  cosine of every pair while saying nothing about the neighbours it is
  meant to compare. They are now left out of the network features. They
  never affected eligibility or labels, which only count links between two
  different topics.
- **2026-10-08, content vectors from the abstracts themselves.** The
  content features were to come from `BAAI/bge-small-en-v1.5`, a pretrained
  embedding model released in 2023. Its paper and model card do not list
  its English training sources, and some embedding models are trained on
  pairs taken from scientific papers, including citation pairs (Nomic
  Embed, for example, lists S2ORC citation pairs among its training data).
  A model trained on citations made after 2017 may have learned which
  fields later cite each other, which would favour exactly the content
  features that H1 tests. The main analysis now uses TF-IDF vectors fitted
  at each cutoff on that cutoff's abstracts only (settings under Data);
  the two content features are computed from them as before. bge-small and
  bge-base become robustness checks. If they help and TF-IDF does not, we
  will report that the gain may come from the models having seen later
  literature. Timing: 239 of the 600 topic snapshots had been collected,
  all at the 2011 cutoff. No model had been fitted and no outcome looked
  at. The only use of the data so far was a check of feature ranges on the
  first 78 topics at the 2011 cutoff, which computed labels in memory
  without printing or summarising them.
- **2026-10-08, usable abstracts only.** OpenAlex marks some records as
  having an abstract when the text is a placeholder ("International
  audience", "Ce texte est disponible en format PDF seulement", retraction
  notices), and about 9% of the sampled texts are mostly in non-Latin
  scripts, with more in French, Spanish or Portuguese. Content vectors
  would then make two topics look alike because both publish in the same
  language, and research communities that share a language also cite each
  other, so content could look predictive for a reason unrelated to what
  the papers say. The rule under Data removes these. Measured on the 246
  topics collected at the 2011 cutoff, it keeps 73% of the texts; 7 topics
  have fewer than 5 usable abstracts. Timing: no model fitted, no outcome
  looked at; the text checks that led here are in the log below.

## Looks at the data before analysis

Every use of the analysis data before the analysis itself, and what was
printed. None of them printed or summarised an outcome.

- 2026-10-07: feature ranges (minimum, median, maximum, missing values) on
  the first 78 topics at the 2011 cutoff, with pretrained embeddings, and
  the number of eligible pairs. Labels were computed in memory only.
- 2026-10-08: the same for the TF-IDF content features on the first 246
  topics at the 2011 cutoff, plus running time and memory, and once more
  after the usable-abstract rule (pair count and missing values only).
  Labels were computed in memory only.
- 2026-10-08: text quality of the same 246 topics' abstracts: counts of
  publisher boilerplate, placeholder and non-English texts, a random sample
  of short texts, the distribution of the share of common English words,
  and how many texts and topics each candidate rule keeps. No citation
  counts were read.

## Deviations

None yet. Any change made after results are seen will be listed here with
its date and reason.
