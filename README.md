# undiscovered

**Finding the research that should be talking to each other — and testing whether we're right.**

In 1986 the information scientist Don Swanson noticed that one body of papers
said fish oil thins the blood and lowers its viscosity, and another said
Raynaud's syndrome involves thick, sluggish blood. Nobody had read both. He
proposed fish oil for Raynaud's; a clinical trial later found it helped. He
called it *undiscovered public knowledge*: findings already published,
waiting in two literatures that never cite each other.

There are now hundreds of millions of papers, and the walls between fields
are higher than ever. **undiscovered** is an open, volunteer-run network that
looks for those connections across *all* sciences, between fields that do not
yet talk, and **publishes how often it is right**.

> **Status: building.** The first milestone is the backtest below — does the
> method beat the published prior art? Its result will be published here
> either way, including if the answer is no.

## How it works

1. **A map of who cites whom.** For every research topic in
   [OpenAlex](https://openalex.org) (an open, CC0 index of about 250 million
   works), which other topics cite its landmark papers, and when.
2. **Candidate bridges.** Pairs of topics from different domains (physical,
   life, health and social sciences) that do not cite each other yet, scored
   on how the citation network is shaped around them and on what their
   papers actually say.
3. **A backtest anyone can rerun.** Freeze the literature at the end of 2017,
   predict which unconnected pairs will start citing each other, and check
   against what happened in 2018–2023. The model is fitted on an earlier
   cutoff (2012), so every reported number is out of time.
4. **Volunteers and experts.** People contribute their own computer and
   **any AI model they like** — local (Ollama, LM Studio, llama.cpp, vLLM) or
   a provider (OpenAI, Anthropic, Google, OpenRouter…) — to judge candidates,
   and researchers rate the bridges in their own field. Hidden test questions
   with known answers measure every contributor's model, so the network can
   trust results from models it has never seen.

It costs nothing to run: open data, GitHub for the site and the
coordination, and contributors' own machines for the work.

## Ways to help (as each part ships)

- **Rate a bridge** — every connection on the site has a "rate this" button;
  if it is your field, your judgment is the most valuable thing here.
- **Ask about your own work** — run the tool on your machine with your paper,
  ORCID or a description, and get the distant fields working on the same
  thing. Private by default.
- **Volunteer** — let your machine and the model of your choice work through
  candidate bridges.

Two interchangeable clients implement the same [protocol](PROTOCOL.md): one in
Python and one in [Aether](https://github.com/aether-lang-dev/aether).

## Standing on

This is not a new idea, and it should not pretend to be. It builds on, and
must beat, earlier work:

- Swanson's literature-based discovery and ARROWSMITH, and the time-sliced
  evaluation that became that field's standard.
- **SciMuse** (Gu & Krenn, 2024): a knowledge graph of 58 million papers and
  GPT-4 proposed cross-domain research ideas; over 100 Max Planck group
  leaders rated 4,000 of them and found a quarter "very interesting". The
  closest work to this one.
- **Science4Cast / Impact4Cast** (Krenn et al., 2023–24): predicting which
  concepts will be studied together, from the shape of a growing knowledge
  graph. Its network features are this project's baseline to beat.
- **Human-aware AI** (Sourati & Evans, *Nature Human Behaviour*, 2023):
  modelling who could plausibly make a discovery improves prediction of
  future discoveries by up to 400%, and points to "alien" hypotheses no one
  is placed to find.
- **mat2vec** (Tshitoyan et al., *Nature*, 2019): embeddings of materials
  abstracts frozen at 2009 predicted thermoelectric materials found years
  later.

What is new here is the combination: open, continuous, across all sciences,
validated in public, and not tied to any one model or company.

## Reproduce the backtest

See [research/README.md](research/README.md).

## Licence

Code: [MIT](LICENSE). Data we publish: [CC0](DATA_LICENSE.md), derived from
OpenAlex (also CC0).
