# Analysis plan for the first backtest

This plan was first committed on 2026-10-07, before any model was fitted
and before any label was computed. It has since been amended several
times, always before any model was fitted and before any outcome was seen.
Every amendment is listed below with its date and reason, and every look at
the data before the analysis is logged. Git history keeps every earlier
version. Anything decided after the results are seen will be listed under
*Deviations* and reported as exploratory. Dates are UTC.

Before this plan was written, the data pipeline was tested on a pilot (40
topics at a 2012 cutoff, 3 at 2017) to check that the OpenAlex queries
return what the design needs. Counts of citing topics per topic were looked
at to check the pipeline; no pair was labelled and nothing was modelled.
The pilot used an earlier version of the pipeline, is not part of the
analysis, and has been deleted.

## Question

Two research topics from different domains (physical, life, health or social
sciences) whose papers have barely cited each other's most cited papers: can
we predict whether they start citing each other within the next six years?

The specific question is whether **what the two topics' papers say** adds
predictive power to **the shape of the citation network around them**. The
network model is the baseline to beat. It uses the kinds of features that
did best in Science4Cast (Krenn et al., *Nature Machine Intelligence*,
2023): degrees, shared neighbours and their growth over time. The best
Science4Cast entries tracked these year by year and used non-linear models;
ours uses one window and its last three years in a logistic regression, so
it is a simpler version of that approach, not a reproduction of one entry.

## Hypotheses

- **H1 (primary).** The `combined` model has a higher average precision than
  the `network` model on the 2017 evaluation. Its outcome is one of three:
  - *supported*: the 95% bootstrap interval of the difference lies above
    zero;
  - *negative*: the interval's upper end is below 10% of the network
    model's average precision, so any gain worth having is ruled out;
  - *inconclusive*: neither.
- **H2 (sanity check).** The `network` model has a higher average precision
  than the `popularity` model. If it does not, the network baseline did not
  work on this data, and H1 is not interpreted.
- **H3 (secondary).** The `semantic` model has a higher average precision than
  the `popularity` model.

## Data

- **Source:** OpenAlex, accessed in October 2026, through the cached client in
  `undiscovered_research/openalex.py`. Each record notes the date it was
  retrieved.
- **Topics:** 75 per domain, 300 in total, drawn with seed 2026 from the 4,516
  OpenAlex topics (`collect.sample_topics`).
- **Topic of a work:** its OpenAlex primary topic.
- **Cutoffs:** 2011 (train window 2004 to 2011, test window 2012 to 2017) is
  used only to fit the models. 2017 (train window 2010 to 2017, test window
  2018 to 2023) is used only to evaluate them. A train window is eight
  calendar years; its last three are the recent window.
- **Reference papers** (`instrument` in the code): for each topic and
  cutoff, its 100 papers published up to the cutoff with the most citations
  made up to the cutoff. They are chosen from the topic's 400 most cited
  papers today, after subtracting each paper's citations from years after
  the cutoff (OpenAlex `counts_by_year`, which starts in 2012). Papers with
  no citations yet are not used.
- **Link from A to B in a window:** works whose primary topic is A, published
  in the window, that cite at least one of B's reference papers. A pair's
  link count is the sum of both directions.
- **Abstracts:** 40 works per topic and cutoff, drawn at random (OpenAlex
  `sample`, seed 17) from the topic's works in the train window that have an
  abstract. Only usable ones count: title and abstract together have at
  least 40 words, and at least a quarter of them are common English words
  (scikit-learn's English stop-word list). A topic with fewer than 5 usable
  abstracts has no content vector, and its pairs are left out for every
  model.
- **Content vectors:** TF-IDF fitted, at each cutoff, on that cutoff's
  usable abstracts and nothing else. Section headings of structured
  abstracts ("Background:", "Results:" and the like) and rights notices are
  removed first. Stop words are scikit-learn's English list without the
  words that carry meaning in some field (system, thin, thick, fire, bill,
  mill, interest, found, detail, computer, empty, fill, full, front, bottom,
  top, side, part, move, describe, show) and with publisher names added
  (copyright, elsevier, springer, wiley, psycinfo, apa, ltd, inc, llc,
  gmbh). Only words of two or more letters count, so no numbers. Sublinear
  term frequency; terms that appear in at least 2 and at most half of the
  abstracts.
- **Size and growth:** a topic's works per year in the train window. Size is
  their sum; growth is the log ratio of works in its last four years to its
  first four.

## Units and labels

- A unit is an unordered pair of sampled topics from different domains.
- A pair is **eligible** if it has at most 1 link in all the years up to the
  cutoff.
- An eligible pair is **positive** if its test-window link count is at least
  3.
- **Stricter label**, for the check in the decision: the same count, but
  only of citing works that are articles or reviews and that OpenAlex does
  not also file under the other topic's subfield (a work has up to three
  topics). It is fetched during the analysis for the 2017 pairs that are
  positive, since no other pair can be positive under it.

## Models

Logistic regression with balanced class weights on standardised features,
fitted on the 2011 cutoff and applied unchanged to the 2017 cutoff. For a
pair, "hi" and "lo" are the larger and smaller of the two topics' values.

- `popularity`: log size hi and lo, growth hi and lo, log number of usable
  abstracts hi and lo, and one indicator for each pair of domains (the first
  left out). Every other model contains these.
- `network`: popularity, plus log degree hi and lo (the number of other
  topics citing each topic's reference papers in the train window), the
  same for the recent window, log number of topics citing both, the same
  for the recent window, Jaccard index, Adamic-Adar (each common citing
  topic weighted by how many sampled topics it cites), the cosine of the
  two citing-topic count vectors, log number of two-step paths through a
  third sampled topic, and the number of earlier links (0 or 1). A topic's
  citations of itself are not part of its neighbourhood.
- `semantic`: popularity, plus the cosine of the two topics' abstract
  centroids and the mean of the five highest cosines between their
  individual abstracts, using at most 20 abstracts per topic so the number
  of comparisons does not grow with a topic's size.
- `combined`: all of the above.

A random score is reported as a floor. The code is
`undiscovered_research/backtest.py`.

## Metrics

- **Primary:** average precision on the 2017 evaluation pairs.
- **Secondary:** ROC-AUC, precision at 100 and at 1,000, and the base rate.
- **Uncertainty:** 2,000 bootstrap replicates of the topics (1,000 for each
  robustness check). In each replicate, the topics of each domain are drawn
  with replacement, as many as the domain has, matching how the sample was
  drawn. Every pair at both cutoffs is weighted by how many times each of
  its two topics was drawn, every model is refitted on the weighted 2011
  pairs, and the weighted 2017 pairs are scored. The intervals therefore
  include the uncertainty of the fitted weights as well as of the
  evaluation. 95% percentile intervals are reported for each model's
  average precision and for the differences between models.

## Decision

- **Continue** to the distributed parts of the project (clients, work units,
  aggregation) only if all three hold: H1 is *supported*, H2 holds, and the
  difference between `combined` and `network` is still above zero under
  the stricter label. The last condition guards against the gain coming
  from papers filed under the wrong topic.
- **Stop and publish the result** otherwise, including when H1 is supported
  but H2 does not hold, and when H1 is *inconclusive*. An inconclusive
  result is reported as inconclusive, not as negative. Features will not be
  tuned on the 2017 evaluation to rescue a result. A redesigned method
  would need a new cutoff that has not been looked at.
- **In every case,** all numbers in this plan are published on the site,
  together with the code and the commit used.

## Robustness checks

These are reported alongside the main result and do not change the
decision:

1. Positive threshold of 2 and of 5 test-window links, instead of 3.
2. Eligibility of 0 links up to the cutoff, instead of at most 1.
3. Pretrained embeddings instead of TF-IDF: `BAAI/bge-small-en-v1.5` and
   `BAAI/bge-base-en-v1.5`. If they help and TF-IDF does not, we will report
   that the gain may come from the models having seen later literature.
4. A second sample of 300 topics, drawn with seed 2027.
5. Results by domain pair (for example life sciences with physical sciences).
6. Only topics with at least 200 works in the train window, at each cutoff.
   Topics that barely existed before the cutoff are the most likely to be
   shaped by how OpenAlex's present-day topics were drawn.
7. H1 under the stricter label, with its interval.

Also reported, as description only: how many positive pairs are linked in
both directions and how many in one; and the mean and spread of every
feature at both cutoffs, to show whether they shifted between them.

## Known limitations

- OpenAlex files works under topics with one present-day classifier, a
  fine-tuned language model that reads each work's title, abstract and
  journal name; about 10% of works have no topic. The classifier was
  trained on recent text, so topics and their boundaries reflect today's
  view of each field. This affects features and labels alike. Robustness
  check 6 and the stricter label address the two ways it is most likely to
  bias the result.
- The reference papers are chosen among a topic's 400 most cited papers
  today. A paper with many citations up to the cutoff but few since could
  in principle fall outside them; this is rare for the top 100.
- A citation is a proxy for one field using another's work. It misses use
  without citation and counts citation without real use.
- 300 of 4,516 topics are sampled. Each sampled topic's citing topics are
  counted in full, but Adamic-Adar, two-step paths and the candidate pairs
  only involve sampled topics.
- The pretrained embedding models in robustness check 3 may have been
  trained on literature from after the cutoff. The main analysis does not
  use them.

## Amendments before analysis

- **2026-10-07, eligibility.** The first version counted links only in the
  train window (eight years), so a pair of topics that cited each other
  heavily before 2010 but rarely in 2010 to 2017 would have counted as
  "unconnected", and its return would have been an easy prediction rather
  than a discovery. Eligibility now counts links in every year up to the
  cutoff, as Science4Cast does when it asks which pairs are still
  unconnected (we still allow one stray citing work). Decided before any
  analysis data was collected.
- **2026-10-07, fitting cutoff 2011 instead of 2012.** With 2012, the
  fitting labels came from 2013 to 2018, which shares the year 2018 with the
  evaluation window. With 2011 they come from 2012 to 2017.
- **2026-10-07, bootstrap over topics instead of pairs.** Pairs that share
  a topic are not independent: if a model misjudges one topic, it misjudges
  all of that topic's pairs together. Resampling pairs would give intervals
  that are too narrow and make H1 easier to pass by chance.
- **2026-10-07, self-citations out of the neighbourhood.** A topic's
  citations of its own reference papers were counted among its citing
  topics. In the pilot they were among a topic's three largest counts for
  34 of 40 topics, so they would have weighed heavily on the co-citation
  cosine. They never affected eligibility or labels.
- **2026-10-08, content vectors from the abstracts themselves.** The
  content features were to come from `BAAI/bge-small-en-v1.5`, a pretrained
  embedding model released in 2023 whose English training sources are not
  documented. Some embedding models are trained on citation pairs from
  scientific papers (Nomic Embed lists S2ORC citation pairs), and a model
  that learned citations made after 2017 would favour exactly the features
  H1 tests. TF-IDF fitted at each cutoff cannot know anything later.
- **2026-10-08, usable abstracts only.** OpenAlex has placeholder abstracts
  ("International audience", "Ce texte est disponible en format PDF
  seulement", retraction notices), and about 9% of the sampled texts are
  mostly in non-Latin scripts, with more in French, Spanish or Portuguese.
  Two topics publishing in the same language would look alike, and
  communities that share a language also cite each other. Measured on 246
  topics at the 2011 cutoff, the rule keeps 73% of the texts; 7 topics have
  fewer than 5 usable abstracts.
- **2026-10-08, wording.** The network model is described as in the style
  of Science4Cast, not as a reproduction of a published method.
- **2026-10-08, after an adversarial review.** Three independent reviews
  (methods, code, and claims) were run before any analysis. These changes
  follow from them:
  - *Reference papers by citations up to the cutoff.* They had been chosen
    by today's citation counts, which include citations made after the
    cutoff, partly by the very pairs the test asks about. For one topic
    checked (T10014), only 53 of the 100 papers chosen this way at 2011,
    and 72 of 100 at 2017, are among its 100 most cited today. All data
    is collected again under the new rule.
  - *A stronger network baseline.* Recent-window degrees and shared
    neighbours, growth, two-step paths and the earlier-link count were
    added, because a baseline weaker than the approach it is named after
    would make H1 easier to pass.
  - *Controls in every model* for the pair of domains and the number of
    usable abstracts, so that content cannot win just by recognising the
    domains or how well a topic is indexed; and at most 20 abstracts per
    topic in the closest-pairs feature.
  - *Cleaner content vectors:* headings and rights notices removed, a stop
    list that keeps meaningful words, publisher names dropped, no numbers.
  - *The stricter label and the check in the decision.* OpenAlex files
    works with a classifier that reads their text, so misfiling is likelier
    between topics whose papers read alike, which is what the content
    features measure.
  - *Three outcomes for H1*, with the smallest effect worth having fixed in
    advance, so that a wide interval is reported as inconclusive rather
    than negative; and the case "H1 holds, H2 does not" stated.
  - *2,000 replicates, drawn within each domain, refitting every model*,
    instead of 300 replicates of a fixed model.
  - *Robustness check 6*, and the descriptive reports on link directions
    and feature shift.
  - *A loader that refuses an incomplete sample or records in an old
    format*, instead of silently using what is there.
  Timing: the data under the old reference-paper rule was complete at 2011
  and at 181 of 300 topics at 2017; it is being replaced. No model had been
  fitted and no outcome had been looked at, apart from the exposure logged
  below.

## Looks at the data before analysis

Every use of the analysis data before the analysis itself, and what was
printed.

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
- 2026-10-07 and 2026-10-08, an exposure: the collector's progress line
  printed, for each topic, how many sampled topics cited it in the test
  window. At the 2017 cutoff that is a per-topic summary of outcomes, not
  of any pair or model. About twenty such lines were seen while checking
  progress. The line no longer prints it, and the data concerned was
  collected under the old reference-paper rule and is being replaced.
- 2026-10-08: structure checks of the collected files (field names,
  windows, file dates, how many topics had no reference papers or no
  abstracts; no citation counts), a dry run of the new collector on one
  topic printing field sizes only, and the reference-paper comparison for
  topic T10014 quoted above.

## Deviations

None yet. Any change made after results are seen will be listed here with
its date and reason.
