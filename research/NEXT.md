# After the first test (draft)

This is not a plan yet. It is written down before the first result exists,
so that what comes next cannot be shaped by that result, and so that it can
be criticised while it is still cheap to change. Each part gets its own
preregistration before any of its data is analysed.

The first test came out inconclusive because too few pairs connected; a
draft for a decisive version, on every topic, is in
[STUDY-2-DRAFT.md](STUDY-2-DRAFT.md).

## 1. A forward test

The backtest checks the past. However careful it is, it was designed by
people who know roughly what happened after 2017, and every pretrained
model has read some of it. A forward test has neither problem: the outcomes
do not exist yet.

- Freeze the literature at the end of 2025 and rank the unconnected pairs
  with the model fitted in the first test, unchanged.
- Publish the ranking as a file, and timestamp its hash with
  [OpenTimestamps](https://opentimestamps.org), which anchors it in the
  Bitcoin blockchain at no cost and without an account. Anyone can later
  check that the ranking existed on that date and has not changed.
- Score it every year as the citations arrive, with a GitHub Action, and
  show the running score on the results page next to the backtest.
- Cost: about 9 OpenAlex calls per topic for the freeze, then about 3 per
  topic each year to score it.

If the backtest works, the forward test checks it on outcomes nobody could
have known. If it does not, the network baseline still gets a forward
record, which is worth having.

## 2. Field-free descriptions

Question: do descriptions of papers written without their field's
vocabulary (see `distill` in [PROTOCOL.md](../PROTOCOL.md)) predict new
cross-field connections better than the abstracts themselves?

- Same question and metrics as the first test, on a fresh sample of
  topics (seed 2028), so nothing is reused from the first test's
  evaluation.
- The hard part is memorisation. A language model describing a 2017 paper
  has read papers from after 2017, and may phrase the description in terms
  that only became common in the field that later took the idea up. That
  would favour the descriptions for the wrong reason. Two designs avoid it,
  and one will be chosen before any description is generated:
  - **Freeze after the model's training data ends.** Use open-weight models
    whose training cutoff is documented, freeze the literature after that
    date, and accept a shorter outcome window.
  - **Forward only.** Generate the descriptions now, for the forward test
    above, and wait for the outcomes.
- Size: about 12,000 descriptions per freeze (300 topics, 40 abstracts
  each), and two freezes in either design (one to fit the model, one to
  test it). By our estimate (2 to 4 seconds per description) 24,000 is
  roughly a day for one consumer GPU running a small local model, or an
  hour for a few dozen volunteers. It is the first job the volunteer
  network would do.

## What we will not do

- Tune anything on the 2017 evaluation, or on any outcome, after seeing it.
- Claim foresight from questions whose answers a model may have read. Known
  answers measure reliability; only forward tests and clean backtests
  measure foresight.
