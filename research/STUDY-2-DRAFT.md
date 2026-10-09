# Second test: draft plan (not yet registered)

A draft for criticism. Nothing in it has been collected or run. When it is
final it will be registered on OSF and committed as a preregistration
before any of its data is collected, as the first test's was.

## Why a second test

The [first test](PREREGISTRATION.md) asked whether what papers say adds to
the citation network in predicting which distant fields start citing each
other. The answer was inconclusive: the difference in average precision was
-0.010 with a 95% interval from -0.050 to +0.045. The interval was wide
because only 305 of 28,114 pairs connected. A test that can answer the
question needs far more pairs.

## How big it has to be

The interval's width comes from the topics: pairs that share a topic move
together, so it shrinks roughly with the square root of the number of
topics. Scaling the first test's interval (about plus or minus 0.048, from
300 topics) that way:

| topics | expected interval on the difference |
|---|---|
| 300 (first test) | about plus or minus 0.048 |
| 1,000 | about plus or minus 0.026 |
| 4,516 (all of them) | about plus or minus 0.012 |

The smallest gain worth having, fixed in the first plan, is 10% of the
network model's average precision, about 0.015. Only the full set of topics
gets the interval below that. This is an estimate from one study; the
registered plan will say so and will not change its size after seeing data.

## Design

- **Topics:** all 4,516 OpenAlex topics.
- **Freezes:** fit at the end of 2012 (outcomes 2013 to 2018), evaluate at
  the end of 2018 (outcomes 2019 to 2024). The first test used 2011 and
  2017; 2018 is a freeze nobody has looked at, as the first plan requires
  for a redesigned test.
- **Data:** the same records as the first test, collected as volunteer map
  units (see [DESIGN.md](../DESIGN.md)): reference papers chosen by
  citations up to each freeze, every citing topic counted in every window,
  plus the outcome window. About 25 OpenAlex calls per topic and freeze:
  roughly 230,000 calls, three weeks for one free key or two days for ten
  volunteers.
- **Labels:** as in the first test, including the stricter label against
  misfiled papers.
- **Models:** gradient-boosted trees (scikit-learn's
  `HistGradientBoostingClassifier`, settings fixed in advance) as the main
  model, because the best Science4Cast entries were non-linear; logistic
  regression as before, as a check. Features: the first test's, plus each
  topic's works per year as separate features, so growth is not reduced to
  one number.
- **Content:** TF-IDF fitted at each freeze on that freeze's abstracts, as
  in the first test, because it cannot know anything written later.
  Descriptions without the field's jargon, written by a language model, are
  left to the forward test ([NEXT.md](NEXT.md)): any model good enough to
  write them has read papers from after 2018, and could leak the answer.
- **Uncertainty and decision:** as in the first test: 2,000 topic-level
  bootstrap draws within each domain, refitting every model; H1 supported,
  negative or inconclusive against the same smallest effect; continue only
  if H1 is supported, the network model beats popularity, and the gain
  holds under the stricter label.

## Questions to settle before registering

1. Is the full set of topics worth three weeks of one key, or should the
   test wait for volunteers?
2. Are the gradient-boosting settings below sensible defaults, with no
   tuning on any outcome? (`max_iter=300`, `learning_rate=0.05`,
   `max_leaf_nodes=31`, `l2_regularization=1.0`, balanced class weights.)
3. Should the evaluation also be run by domain pair as a primary result,
   since the network model's strength differed by domain pair in the first
   test?
