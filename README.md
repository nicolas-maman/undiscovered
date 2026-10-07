# undiscovered

An open network that looks for research in one field that another field
could use but has never cited, and measures how often it is right.

## The idea

In 1986 the information scientist Don Swanson read two sets of papers that
had never cited each other. One showed that dietary fish oil lowers blood
viscosity, reduces platelet aggregation and dampens vascular reactivity. The
other described patients with Raynaud's syndrome, whose condition involves
high blood viscosity, platelet aggregation and vascular reactivity. Swanson
proposed fish oil as a treatment. Three years later a double-blind trial
(DiGiacomo, Kremer & Shah, *American Journal of Medicine*, 1989) found it
helped. He called this *undiscovered public knowledge*: results that are
already published, but in literatures that nobody reads together.

Swanson worked by hand, in medicine. This project tries to do the same thing
across all of science, openly, and checks its own predictions against what
actually happened.

> **Status, October 2026: collecting the data for the first test.** The
> analysis plan, including the rule that decides whether the method works,
> was [published before any data was analysed](research/PREREGISTRATION.md).
> The result will appear on the
> [results page](https://nicolas-maman.github.io/undiscovered/results.html)
> whether or not the method works.

## How it works

1. **A map of who cites whom.** [OpenAlex](https://openalex.org), a free and
   open index of scholarly works, assigns every paper to research topics. For
   each topic we record which other topics cite its most cited papers, and
   in which years.
2. **Candidate pairs.** Two topics from different domains (physical, life,
   health or social sciences) that barely cite each other yet. Each pair is
   scored on the shape of the citation network around it and on how close
   the two topics' papers are in content.
3. **A backtest anyone can rerun.** We freeze the literature at the end of
   2017, rank the unconnected pairs, and check which of them did start citing
   each other between 2018 and 2023. The model learns its weights on an
   earlier freeze (2011, with outcomes from 2012 to 2017), so nothing after
   2017 goes into it.
4. **Volunteers and experts.** Once the backtest is done, anyone will be able
   to lend their computer and whichever AI model they prefer, local or from
   a provider, to examine candidate pairs. Researchers will be able to rate
   the pairs that touch their own field. Questions with known answers, mixed
   into the work, measure how reliable each contributor's model is.

Running it costs nothing: the data is open, the site and the coordination
run on GitHub, and the work runs on contributors' own machines.

## Ways to help

**Now: find a flaw in the plan.** Read the
[analysis plan](research/PREREGISTRATION.md) and
[tell us what could make the result wrong](https://github.com/nicolas-maman/undiscovered/issues/new?template=plan-review.yml). Criticism is worth most
before the data is analysed, while the plan can still change in the open.

As each part ships:

- **Rate a pair.** If a proposed connection touches your field, your view of
  whether it is real is the most useful input the project can get.
- **Ask about your own work.** Run the tool on your machine with a paper, an
  ORCID or a short description, and see which distant fields work on the
  same problem. Nothing leaves your machine unless you choose to share it.
- **Volunteer.** Let your machine and the model of your choice work through
  candidate pairs.

Two clients will implement the same [protocol](PROTOCOL.md): one in Python
and one in [Aether](https://github.com/aether-lang-dev/aether).

## Earlier work

The idea is not new. This project builds on the work below. Its backtest has
to beat a baseline built on the network features that did best in
Science4Cast to be worth anything.

- **Literature-based discovery.** Swanson's method and his ARROWSMITH
  software, and the time-sliced evaluation that later became the field's
  standard test.
- **SciMuse** (Gu & Krenn, 2024). A knowledge graph built from 58 million
  papers and GPT-4 generated personalised research ideas. More than 100
  research group leaders at the Max Planck Society scored over 4,400 of them;
  24.9% received 4 or 5 out of 5. The closest work to this one.
- **Science4Cast** (Krenn et al., *Nature Machine Intelligence*, 2023). A
  benchmark for predicting which concepts will be studied together, built
  from more than 143,000 AI papers. Its finding that carefully chosen network
  features beat end-to-end learning is why those features are our baseline.
- **Human-aware AI** (Sourati & Evans, *Nature Human Behaviour*, 2023).
  Modelling which scientists could plausibly make a discovery improved the
  prediction of future discoveries by up to 400%.
- **mat2vec** (Tshitoyan et al., *Nature*, 2019). Word embeddings trained on
  materials-science abstracts published before 2009 identified thermoelectric
  materials that were only reported years later.

What this project adds is the combination: open code and data, all fields
rather than one, a public backtest, and no dependence on a particular model
or company.

## Reproduce the backtest

See [research/README.md](research/README.md).

## Licence

Code: [MIT](LICENSE). Data published by the project: [CC0](DATA_LICENSE.md),
derived from OpenAlex, which is also CC0.
