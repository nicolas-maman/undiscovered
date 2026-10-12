# How the distributed version works

Written in October 2026, after the first test, and kept up to date as
parts ship. [PROTOCOL.md](PROTOCOL.md) has the message formats; this
document has the shape of the whole.

## What it is for

A researcher opens the site, finds their own field, and sees papers in
distant fields that work on the same problem, and pairs of fields likely to
connect next. Each suggestion shows its evidence, says which AI models were
involved, and shows how experts in the two fields rated it.

Three kinds of people make that:

- **volunteers**, who lend their computer and an AI model of their choice,
  on their own machine or free in the cloud;
- **experts**, who rate the suggestions that touch their own field;
- **the project**, which runs only free GitHub services: a website, a
  public inbox for results and ratings, and jobs that check and combine
  them.

The crowd comes first. What volunteers produce together (an open index of
papers described in plain words, the pairs of papers it brings together,
and a public comparison of AI models on this task) is what is then put in
front of researchers.

## What the first test settled, and what it did not

- **Settled:** the citation network around two topics predicts whether
  they will start citing each other. On 28,114 pairs of topics from
  different domains, the network model ranked the pairs that connected
  about 14 times better than chance, and 30 of its top 100 did connect; on
  a second, independent sample of 300 topics, about 16 times.
- **Settled, negatively:** comparing the topics' abstracts by the words
  they share added nothing measurable. That method is not used here.
- **Not tested yet:** whether descriptions of papers without their field's
  jargon find better matches, and whether AI-written explanations are
  right. This design measures both in public (see *How we will know it
  works*), and labels everything AI-written as untested until then.

## The parts

### 1. Describe (volunteers, any AI model): live

Fields often name the same problem differently. A volunteer's model reads a
paper's title and abstract and writes, in two plain sentences, the problem
it works on and how, without the paper's distinctive words.

- **Papers.** The sampled papers of the first test's 300 topics up to
  2025 that are research and have a usable abstract: 8,049, in 403 units of
  20, on the `distill-2025` branch; and 86 papers of a published benchmark
  of cross-field twins, in 18 more units among ordinary papers, for the
  first test of the descriptions ([research/KNOWN-TWINS.md](research/KNOWN-TWINS.md)).
  Each unit lists, for each paper, its distinctive words; the model is told
  to avoid them.
- **Models.** Any: on the volunteer's machine (Ollama, LM Studio,
  llama.cpp, vLLM, Jan), free in the cloud (Gemini, Groq, OpenRouter,
  Mistral), or paid. Every description records its model.
  [docs/MODELS.md](docs/MODELS.md) compares the options.
- **Checks.** Before sending, the client checks each answer as the project
  will, and asks the model again once if it fails; the project's job then
  checks every result with the same code: two short parts, at most two of
  the paper's distinctive words, and no description repeated for another
  paper. Each unit needs two volunteers.

### 2. Combine (one job, after every accepted result): live

The job rebuilds, on the data branch:

- **the open index**: every accepted description, with its model, under
  CC0;
- **models compared**: how well each model's descriptions agree with
  other models' descriptions of the same papers, against chance. Two
  volunteers running the same model do not count as agreeing;
- **pairs of papers** from different domains whose descriptions are most
  alike, using only papers that two different models describe
  consistently, so that a vague description cannot make a pair.

The site shows them on [Same problem, different field](https://nicolas-maman.github.io/undiscovered/connections.html),
and progress on [Take part](https://nicolas-maman.github.io/undiscovered/join.html).
Similarity is TF-IDF cosine for now: simple, and anyone can recompute it.

### 3. Map (volunteers, no AI needed): live

For the ranking of pairs of fields, every topic needs a record of which
other topics cite its most cited papers, now and in recent years: the same
record the first test collected, at the end of 2025.

- **Size.** About 17 to 25 OpenAlex calls per topic, about 100,000 for all
  4,516 topics: ten days for one free key, a day for ten volunteers. This
  job needs no model, so it suits volunteers without one.
- **Submission and checks.** A unit's ten records go in a gist under the
  volunteer's account, named in a short issue with a checksum. The job
  validates every record, and gives 1 unit in 20 to a second volunteer to
  compare.

### 4. Rank: the forward test is registered

- **The forward test** ([plan](research/FORWARD-TEST.md)): the
  first test's network model, unchanged, ranks the pairs among its 300
  topics at the end of 2025. The ranking is published with a timestamp
  before any of the citations that score it exist, and is scored every
  year. Registered on 12 October 2026; the ranking, both models and the
  records are in [forward/](forward/), with checksums and an
  OpenTimestamps proof.
- **All topics, later.** Two of the model's features count through the
  other topics in the sample, so on the full map they would take larger
  values than the model learned. Either they are computed through the same
  300 reference topics, or the model is refitted on a full map of an
  earlier freeze; whichever is chosen is tested on the backtest data before
  a full ranking is published.

### 5. Review (experts): next

- The site lists pairs by field, with their evidence, which models were
  involved, and the ratings so far.
- An expert rates a pair from 1 to 5 with a prefilled GitHub issue form.
  Ratings by people who work in one of the two fields count most; sign-in
  with ORCID to check that is planned ([issue #1](https://github.com/nicolas-maman/undiscovered/issues/1)).
- Ratings, like everything else, are public.

## How we will know it works

- **Models against chance**: live. A model whose descriptions agree with
  other models' no more than descriptions of different papers do is
  writing nothing specific.
- **Known twins**: in the units now ([plan](research/KNOWN-TWINS.md)). Pairs
  of papers already known to solve the same problem in different fields,
  mixed into units, show whether descriptions bring them together better
  than the abstracts do. Known answers measure reliability only: a model
  trained on later papers may remember them.
- **Experts against chance**: with the review page. The queue mixes in,
  without marking them, pairs drawn at random. SciMuse found that pairs
  predicted to be highly cited were, if anything, rated less interesting
  than random ones, so this is measured from the start.
- **The forward test**: scored every year against the citations that
  actually arrive.

## What it costs

Nothing for the project. GitHub Pages (sites up to 1 GB, a soft limit of
100 GB of traffic a month), GitHub Actions on a public repository, issues,
gists and branches are free. OpenAlex is free, with a free key giving each
volunteer about 10,000 calls a day. Volunteers who choose a paid AI model
pay for their own calls; a local model costs only electricity, and several
cloud services have free tiers.

## Order of work

Done:

1. This document, the protocol, and the first test (published, with all
   its robustness checks).
2. Map units: the Python and Aether clients, the checking job, the data
   branch.
3. Describing units in the Python client, with any model; the checking and
   combining jobs; the Take part and Same problem, different field pages.
4. The forward test's records and ranking code.
5. Describing units in the Aether client, and the known twins in the
   describing units, with the code that computes their result.
6. The forward test, registered and its ranking published.

Next:

7. The yearly count that scores the forward test, from 2027.
8. The review page, the rating form, and the random-pair control.
