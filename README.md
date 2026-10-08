# undiscovered

An open network that looks for research in one field that another field
could use but has never cited, and measures how often it is right.

## The idea

In 1986 the information scientist Don Swanson read two sets of papers that
had never cited each other. One showed that dietary fish oil lowers blood
viscosity, reduces platelet aggregation and dampens vascular reactivity. The
other described patients with Raynaud's syndrome, whose condition involves
high blood viscosity, platelet aggregation and vascular reactivity. Swanson
proposed fish oil as a treatment. Three years later a small double-blind
trial (32 patients; DiGiacomo, Kremer & Shah, *American Journal of
Medicine*, 1989) found that it helped patients with primary Raynaud's,
though not those whose Raynaud's came from another disease. He called this
*undiscovered public knowledge*: results that are already published, but in
literatures that nobody reads together.

Swanson worked by hand, in medicine. This project tries to do the same thing
for every field of science, openly, and checks its own predictions against
what actually happened.

> **Status, October 2026: collecting the data for the first test.** The
> analysis plan, including the rule that decides whether the method works,
> was [published before any model was fitted or any outcome was
> seen](research/PREREGISTRATION.md); every later change to it is dated.
> The result will appear on the
> [results page](https://nicolas-maman.github.io/undiscovered/results.html)
> whether or not the method works.

## How it works

1. A map of who cites whom. [OpenAlex](https://openalex.org), a free and
   open index of scholarly works, assigns about nine in ten works to
   research topics. For each topic we take the 100 papers most cited up
   to the freeze, and record which other topics cite them and in which
   years.
2. Candidate pairs: two topics from different domains (physical, life,
   health or social sciences) whose papers have barely cited each other's
   most cited papers yet. Each pair is scored on the shape of the citation
   network around it and on how close the two topics' papers are in
   content.
3. A backtest anyone can rerun. We freeze the literature at the end of
   2017, rank the unconnected pairs, and check which of them did start
   citing each other between 2018 and 2023. The ranking model learns its
   weights on an earlier freeze (2011, with outcomes from 2012 to 2017).
   One input still comes from today's OpenAlex: the topic each paper is
   filed under. The plan says how that is checked.
4. Next: the problem, without the jargon. Fields often name the same
   problem differently: estimating a hidden state from noisy measurements
   is a Kalman filter to a control engineer and data assimilation to a
   weather forecaster (the example is Kulikowski's). A language model can
   rewrite a paper as the problem it solves, without its field's
   vocabulary. In a recent preprint this raised the average precision of
   matching papers on the same problem across fields from 0.22 to 0.51, on
   109 papers (Kulikowski, 2026). That is one model call per paper: too
   many for one project, but manageable when many volunteers each run their
   own model, local or from a provider. The descriptions would go into an
   open index. Whether they predict new connections better than abstracts
   will be tested like the backtest above, on years and topics it has not
   used ([draft](research/NEXT.md)).
5. Experts and checks. Researchers rate the proposed connections that touch
   their own field, because a connection that will happen is not always one
   worth making (see SciMuse below). Every description and verdict records
   which model produced it. Questions with known answers, mixed into the
   work, and agreement between different models measure how far to trust
   each one.

It costs the project nothing: the data is open, the site and the
coordination run on GitHub, and the work runs on contributors' own machines.
Contributors who choose a paid model pay for their own calls.

## Ways to help

Now: find a flaw in the plan. Read the
[analysis plan](research/PREREGISTRATION.md) and
[tell us what could make the result wrong](https://github.com/nicolas-maman/undiscovered/issues/new?template=plan-review.yml).
Criticism is worth most before the data is analysed, while the plan can
still change in the open.

As each part ships, you will be able to:

- rate the proposed connections that touch your field;
- run the tool on your own machine with a paper, an ORCID iD or a short
  description, and see which distant fields work on the same problem.
  Nothing leaves your machine unless you choose to share it;
- lend your machine and the model of your choice to describe papers and
  examine candidate pairs.

Two clients will implement the same [protocol](PROTOCOL.md): one in Python
and one in [Aether](https://github.com/aether-lang-dev/aether).

## Earlier work

The idea is not new. This project builds on the work below. Its backtest has
to beat a baseline built on the kinds of network features that did best in
Science4Cast, including how fast topics and their neighbourhoods grow,
though in a simpler model than the best entries used.

- Literature-based discovery: Swanson's method and his ARROWSMITH software,
  and the time-sliced evaluation that later became a common test.
- mat2vec (Tshitoyan et al., *Nature*, 2019). Word embeddings trained on
  materials-science abstracts published before 2009 identified thermoelectric
  materials that were only reported years later.
- Bridger (Portenoy et al., CHI 2022). Describes authors by the problems and
  methods in their papers, and suggests authors who share some of them but
  sit outside a researcher's usual circles. In user studies with computer
  scientists, its suggestions were judged more interesting and novel than
  those of a relevance-focused baseline.
- Science4Cast (Krenn et al., *Nature Machine Intelligence*, 2023). A
  benchmark for predicting which concepts will be studied together, built
  from more than 143,000 AI papers. Its finding that carefully chosen network
  features beat end-to-end learning is why those features are our baseline.
- Human-aware AI (Sourati & Evans, *Nature Human Behaviour*, 2023).
  Modelling which scientists could plausibly make a discovery improved the
  prediction of future discoveries by up to 400%.
- SciMuse (Gu & Krenn, 2024, revised 2026). A knowledge graph built from 58
  million papers and GPT-4 generated personalised research ideas. More than
  100 research group leaders at the Max Planck Society scored over 4,400 of
  them: the mean was 2.40 out of 5, and 24.9% received 4 or 5. Choosing
  concept pairs with the knowledge graph did not make ideas more interesting
  than giving the model paper titles alone, and pairs predicted to be highly
  cited leaned slightly less interesting. Predicting a connection is not the
  same as finding one worth making, which is why expert ratings are part of
  this project.
- Idea-Catalyst (Kargupta et al., 2026). Restates a research goal as
  problems free of any one field's terms and looks for how other disciplines
  have approached them. It reports gains of 21% in novelty and 16% in
  insightfulness.
- Same Problem, Different Field (Kulikowski, 2026, preprint). Rewrites each
  paper, with one language-model call, as the computation it performs
  without its field's vocabulary. On 109 papers from 18 method families this
  raised cross-field retrieval average precision from 0.222 to 0.513, while
  four trained scientific embedding models did worse than simple word
  matching (TF-IDF) on the abstracts: they capture topic and citation
  closeness, which is the wrong signal for this task.

What is new here: a public test, written down in advance and run on topics
from every domain of science, of whether such connections can be predicted
before they happen; an open index of field-free problem descriptions, built
by volunteers with whatever model they choose; and expert ratings that
anyone can inspect. No step depends on one AI model or provider.

## Reproduce the backtest

See [research/README.md](research/README.md).

## Licence

Code: [MIT](LICENSE). Data published by the project: [CC0](DATA_LICENSE.md),
derived from OpenAlex, which is also CC0.
