# Forward test: draft plan (not yet registered)

A draft for criticism. Nothing in it has been ranked yet. When it is final
it is committed as a plan, and its ranking is published and timestamped
before any of the outcomes it predicts are counted.

Where it stands (11 October 2026): the 300 topic records at the 2025 freeze
are collected and pass the same checks as volunteers' map results; the
ranking code (`undiscovered_research/forward.py`) computes the first test's
features from them, and on the first test's own 2017 records it reproduces
that test's eligible pairs and every feature value exactly. No ranking of
2025 has been computed, and none will be before this plan is registered.

## Why

The first test checked the past. However carefully it was run, the people
who designed it know roughly what happened after 2017. A forward test does
not have that problem: it ranks pairs of fields now, and the citations that
score it have not been written yet.

What it tests is the part of the first test that worked. Ranked by the
citation network around them, the pairs that went on to connect came out
about 14 times better than chance, and better than a ranking by the size
and growth of the two topics (average precision 0.149 against 0.051;
difference +0.098, 95% interval +0.031 to +0.191). Content did not add to
that, so it is left out here.

## What is ranked

- **Topics:** the first test's 300 (75 per domain, seed 2026). Two of the
  model's features, Adamic-Adar and two-step paths, count through the other
  topics in the sample, so they mean the same thing here as when the model
  was fitted only if the sample is the same.
- **Freeze:** the end of 2025. Each topic's record is collected with the
  volunteer client's own code (`clients/python`, map records, format 1;
  [docs/DATA.md](../docs/DATA.md)): its 100 papers most cited up to 2025,
  the topics citing them in each window, its works per year and its usable
  abstracts. About 17 OpenAlex calls a topic, about 5,200 in all (measured):
  one day of one free key.
- **Pairs:** every pair of those topics from different domains with at most
  one citing work between them in all the years up to 2025, both with at
  least 5 usable abstracts, as in the first test.
- **Model:** the `network` model of the first test, unchanged: logistic
  regression on the same features, fitted on the same 2011 pairs. It is
  refitted from the published 2011 records with the first test's code, and
  its coefficients must agree with those in `data/backtest.json` to within
  0.0001 before anything is ranked. A trial refit on 11 October 2026, on the
  same 28,710 pairs, agreed to within 0.0000025 (the order of floating-point
  sums differs with the number of cores). The `popularity` model is fitted
  the same way, as the comparison.

## What is published, and when

Within two weeks of registering this plan, in `forward/`:

- the 300 topic records at the 2025 freeze;
- `model.json`: both models in full (coefficients, intercept, and the
  feature means and scales they were fitted with), so anyone can score a
  pair without our code;
- `ranking-2025.csv`: every eligible pair with both models' scores;
- `SHA256SUMS` for those files, timestamped with
  [OpenTimestamps](https://opentimestamps.org). The proof is committed next
  to it. It shows the files existed on that date, without trusting us or
  GitHub. It is free and needs no account.

## Outcome and score

- **Connected:** a pair whose topics' papers are cited, in either
  direction, by at least 3 works published from 2026 to 2031: the first
  test's label, with the same six-year window after the freeze.
- **Counted** once a year, from 2027, by a GitHub Action, with a call or
  two per topic. The yearly counts are interim and are labelled
  as such. The result is the count read in mid-2032, once 2031 is fully
  indexed.
- **Measures:** average precision of each model's ranking, chance (the
  share of pairs that connect), precision at 100, ROC AUC.
- **Hypothesis:** the network ranking has a higher average precision than
  the popularity ranking, with the 95% interval of the difference above
  zero (2,000 bootstrap draws of topics within each domain; the models are
  fixed in advance, so they are not refitted in each draw).

Nothing in the plan, the models or the ranking changes after it is
registered. If OpenAlex changes in a way that stops the outcome from being
counted as written, the change and what was done about it are dated in this
file, and the result says so.

## Papers from 2026

The plan is written in October 2026, when part of 2026 has already been
published. The ranking cannot have been shaped by it: it is fixed by
published code, the published 2011 records and works up to 2025, and
anyone can recompute it from those. As a second check, the score is also
reported for the window from 2027 to 2032, which starts after the ranking
is timestamped.

## What it costs

About 5,200 OpenAlex calls once (already spent), then 300 to 600 a year.
Both fit in the free allowance of one key.

## Questions to settle before registering

1. Run it now on the first test's 300 topics, rather than wait for the
   volunteers' map of every topic? The full map would give a ranking of
   all fields, but it needs the model question in
   [DESIGN.md](../DESIGN.md) settled first, and every month of waiting is
   a month of outcomes nobody predicted in public.
2. Is the six-year window from 2026 right as the main result, with 2027 to
   2032 as the check, or should it be the other way round?
