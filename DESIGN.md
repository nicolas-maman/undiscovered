# How the distributed version works (draft)

Written in October 2026, after the first test. It describes what will be
built and in what order. [PROTOCOL.md](PROTOCOL.md) has the message
formats; this document has the shape of the whole.

## What it is for

A researcher opens the site, finds their own field, and sees a short list of
distant fields, and specific papers in them, that may bear on their work.
Each suggestion comes with a plain reason, says which AI models wrote it,
and shows how experts in the two fields rated it.

Three kinds of people make that list:

- **volunteers**, who lend their computer, their free OpenAlex allowance
  and, if they like, an AI model of their choice;
- **experts**, who rate the suggestions that touch their own field;
- **the project**, which runs only free GitHub services: a website, a
  public inbox for results and ratings, and scheduled jobs that check and
  combine them.

## What the first test settled, and what it did not

- **Settled:** the citation network around two topics predicts whether
  they will start citing each other. On 28,114 pairs of topics from
  different domains, the network model ranked the pairs that connected
  about 14 times better than chance, and 30 of its top 100 did connect.
  So the network model can choose which pairs are worth a closer look.
- **Settled, negatively:** comparing the topics' abstracts by the words
  they share added nothing measurable. That method is not used here.
- **Not tested yet:** whether AI-written explanations are right, and
  whether descriptions of papers without their field's jargon find better
  pairs. This design measures both in public (see *How we will know it
  works*), and labels everything AI-written as untested until then.

## The four steps

### 1. Map (volunteers, no AI needed)

The ranking needs, for every topic, which other topics cite its most cited
papers, now and in recent years. That is the same record the backtest
collected, taken at the end of 2025, except that only the number of usable
abstracts is kept, not their text.

- **Size.** About 15 OpenAlex calls per topic, about 70,000 for all 4,516
  topics: a week for one free key, a day for ten volunteers.
- **Unit of work.** 10 topics. The client fetches them with the
  volunteer's own OpenAlex allowance, runs at low priority, and stops
  cleanly when the day's allowance is spent.
- **Submission.** A unit's records are too large for an issue (about
  500 KB; an issue holds 65,536 characters). The client puts them in a
  gist under the volunteer's GitHub account and opens a short issue with
  the gist's address and a checksum.
- **Checks.** A job fetches the gist, validates every record against the
  schema, and sends 1 unit in 20 to a second volunteer; the two must
  match within the small drift of a live index. A volunteer whose units
  fail the comparison is set aside.
- **Storage.** Accepted records are combined into one compressed file
  attached to a GitHub release (files there can be 2 GB), not committed to
  the repository, which would grow too large.

### 2. Rank (one scheduled GitHub job)

- The network model from the first test scores every pair of topics from
  different domains, about 7.3 million pairs, and publishes the top few
  thousand as `candidates.json`.
- **Open question, settled before anything is published:** two features
  (Adamic-Adar and two-step paths) count through other topics, and the
  model learned them on a 300-topic sample. On the full map they would
  count through all 4,516 topics and take larger values. Either they are
  computed through the same 300 reference topics, or the model is refitted
  on a full map of an earlier freeze. Whichever is chosen is tested
  against the backtest data first.
- The ranking is also the forward test of [research/NEXT.md](research/NEXT.md):
  it is timestamped when published and scored every year.

### 3. Explain (volunteers, any AI model)

For each candidate pair, in rank order:

1. The client samples about 40 recent abstracts from each topic.
2. The volunteer's model rewrites each one without its field's vocabulary
   (the `distill` unit in PROTOCOL.md).
3. The client finds the three closest pairs of papers across the two
   topics, using any embedding model or plain word weights.
4. The model writes two sentences on why the connection could matter, or
   says there is none.

Each pair goes to three volunteers using, where possible, different models.
Every paper they cite must exist in OpenAlex and belong to the right topic;
answers that disagree are flagged, not averaged away.

### 4. Review (experts)

- The site lists candidates by field. A card shows the two fields, the
  three paper pairs with links, the reason, which models wrote it, and the
  ratings so far.
- An expert rates a card from 1 to 5 with a prefilled GitHub issue form.
  Ratings by people who work in one of the two fields count most; sign-in
  with ORCID to check that is planned ([issue #1](https://github.com/nicolas-maman/undiscovered/issues/1)).
- Ratings, like everything else, are public.

## How we will know it works

- **Experts against chance.** The review queue mixes in, without marking
  them, pairs of topics drawn at random. If experts rate the ranked
  candidates no better than random pairs, the ranking is not useful to
  them, whatever it predicts. SciMuse made this comparison and found that
  pairs predicted to be highly cited were, if anything, rated less
  interesting than random ones, so it is measured here from the start.
- **The forward test.** The published ranking is scored every year against
  the citations that actually arrive.
- **Models against each other.** Agreement between different models, and
  their accuracy on pairs with known outcomes, give each model a public
  record. Known outcomes measure reliability only: a model trained on later
  papers may remember them.

## Using it

- **Volunteers:** install the client, then run `undiscovered work`. The
  first run asks three things and remembers them on the volunteer's
  machine only: a GitHub login (through the GitHub command-line tool), an
  OpenAlex key (optional), and an AI model (it finds a local Ollama on its
  own, or takes any provider's address and key; only needed for step 3).
  It runs at low priority, uses at most half the processor, and deletes
  its caches when a unit is done.
- **Experts:** the website and a GitHub account.
- **Researchers:** `undiscovered ask` with a paper, an ORCID iD or a short
  description runs privately on their machine and shows the distant topics
  and papers closest to it.

## What it costs

Nothing for the project. GitHub Pages (sites up to 1 GB, a soft limit of
100 GB of traffic a month), GitHub Actions on a public repository, issues,
gists and releases are free. OpenAlex is free, with a free key giving each
volunteer about 10,000 calls a day. Volunteers who choose a paid AI model
pay for their own calls; a local model costs only electricity.

## Order of work

Each step is usable on its own and is released before the next starts.

1. This document.
2. Map units, the Python client (`work` for map units), the checking job,
   and the release with the full map.
3. The ranking job and the public candidate list, after the open question
   in step 2 of the design is settled on the backtest data.
4. Explain units in the client, and the checks on them.
5. The review page, the rating form, and the random-pair control.
6. The Aether client, with the same commands.
