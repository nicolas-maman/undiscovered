# undiscovered

Research in one field that another field could use, but has never cited.

**[See the site](https://nicolas-maman.github.io/undiscovered/)** ·
[Take part](https://nicolas-maman.github.io/undiscovered/join.html) ·
[Results](https://nicolas-maman.github.io/undiscovered/results.html)

Fields often solve the same problem under different names, and rarely read
each other. This open project looks for those connections across all of
science, and checks its predictions against what actually happens next.

## What a connection looks like

Known cases, where the same idea was worked out in fields that call it by
different names:

- **Each event makes the next one more likely, nearby and soon.** The
  model of earthquake aftershocks
  ([Nandan et al., 2017](https://openalex.org/W2625813022)) also describes
  how crime clusters ([Mohler et al., 2011](https://openalex.org/W2123906784)).
- **Estimate what you cannot see from noisy measurements.** The Kalman
  filter tracks the state of a power grid
  ([Bhusal and Gautam, 2020](https://openalex.org/W3112152739)), forecasts
  flu seasons ([Shaman and Karspeck, 2012](https://openalex.org/W2143469080))
  and estimates ice sheets ([Kyanjo et al., 2026](https://openalex.org/W7147738061)).
- **Something matters if things that matter point to it.** PageRank ranks
  web pages ([Avrachenkov et al., 2014](https://openalex.org/W2952548632)),
  football teams ([Lazova and Basnarkov, 2015](https://openalex.org/W1522660207))
  and the amino acids that carry a signal through a protein
  ([Negre et al., 2017](https://openalex.org/W2621651488)).

They come from the benchmark of Kulikowski (2026), *Same Problem, Different
Field* (CC BY 4.0), and are the first test of the describing work below.

## Where it stands

- **First test, October 2026: inconclusive.** Frozen at the end of 2017,
  the citation network around 28,114 pairs of topics from different domains
  ranked the 305 that connected by 2023 about 14 times better than chance.
  Adding the words the papers share did not measurably improve on that, and
  a second, independent sample of 300 topics gave the same answer
  ([results](https://nicolas-maman.github.io/undiscovered/results.html),
  [plan](research/PREREGISTRATION.md)).
- **Forward test, registered 12 October 2026.** The same model ranked
  26,475 pairs of topics at the end of 2025. Its checksums are timestamped
  in Bitcoin block 971017, before any citation that will judge it exists,
  and it is scored on the citations of 2026 to 2031
  ([what was ranked](https://nicolas-maman.github.io/undiscovered/forward.html),
  [plan](research/FORWARD-TEST.md)).
- **Describing papers, open now.** Volunteers' AI models rewrite papers
  without their field's jargon, so that work on the same problem in
  different fields can be matched
  ([take part](https://nicolas-maman.github.io/undiscovered/join.html)).

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

## How it works

1. A map of who cites whom. [OpenAlex](https://openalex.org), a free and
   open index of scholarly works, assigns about nine in ten works to
   research topics. For each topic we take the 100 papers most cited up
   to the freeze, and record which other topics cite them and in which
   years. Volunteers collect this map on their own computers, with their
   own free OpenAlex allowance ([client](clients/python/README.md)); this
   job needs no AI model.
2. Candidate pairs: two topics from different domains (physical, life,
   health or social sciences) whose papers have barely cited each other's
   most cited papers yet. Each pair is scored on the shape of the citation
   network around it. Adding how alike the two topics' abstracts are, word
   for word, did not help in the first test.
3. A backtest anyone can rerun. We freeze the literature at the end of
   2017, rank the unconnected pairs, and check which of them did start
   citing each other between 2018 and 2023. The ranking model learns its
   weights on an earlier freeze (2011, with outcomes from 2012 to 2017).
   One input still comes from today's OpenAlex: the topic each paper is
   filed under. The plan says how that is checked. A forward test, with no
   hindsight at all, was registered on 12 October 2026: the same model
   ranked pairs at the end of 2025, and the ranking, published with a
   timestamp before its outcomes exist, is scored on citations from 2026 to
   2031 ([forward/](forward/)).
4. The problem, without the jargon. Fields often name the same
   problem differently: estimating a hidden state from noisy measurements
   is a Kalman filter to a control engineer and data assimilation to a
   weather forecaster (the example is Kulikowski's). A language model can
   rewrite a paper as the problem it solves, without its field's
   vocabulary. In a recent preprint this raised the average precision of
   matching papers on the same problem across fields from 0.22 to 0.51, on
   109 papers (Kulikowski, 2026). That is one model call per paper: too
   many for one project, but manageable when many volunteers each run their
   own model, local or free in the cloud, and that is the work volunteers
   do now ([take part](https://nicolas-maman.github.io/undiscovered/join.html)).
   The descriptions go into an open index, and papers far apart that are
   described alike are shown as pairs
   ([same problem, different field](https://nicolas-maman.github.io/undiscovered/explore.html#pairs)).
   Any model good enough to write them has read papers from after any past
   freeze, so whether they predict connections is tested forward: described
   now, judged on the citations that arrive later ([draft](research/NEXT.md)).
5. Experts and checks. Researchers rate the proposed connections that touch
   their own field, because a connection that will happen is not always one
   worth making (see SciMuse below). Every description and verdict records
   which model produced it. Agreement between different models, measured
   against chance, and, next, pairs with known answers mixed into the work
   measure how far to trust each one.

It costs the project nothing: the data is open, the site and the
coordination run on GitHub, and the work runs on contributors' own machines.
Contributors who choose a paid model pay for their own calls.

## Ways to help

Now:

- [Describe papers in your browser](https://nicolas-maman.github.io/undiscovered/describe.html):
  nothing to install; the model runs in the page, or you use your own key
  (Google, Groq and OpenRouter give free ones). Or
  [use the command-line client](https://nicolas-maman.github.io/undiscovered/join.html#terminal)
  for many units unattended.
- [Explore](https://nicolas-maman.github.io/undiscovered/explore.html): the map
  of every paper, the pairs across fields and the words that made them, a
  search by what papers do, and everything the checking job has accepted or
  turned away.
- Find a flaw in the [first test's results](https://nicolas-maman.github.io/undiscovered/results.html)
  or the [forward test's plan](research/FORWARD-TEST.md), and
  [tell us what could make a result wrong](https://github.com/nicolas-maman/undiscovered/issues/new?template=plan-review.yml).
  Criticism of a plan is worth most before its data is collected, while it
  can still change in the open.

As each part ships, you will be able to:

- rate the proposed connections that touch your field;
- run the tool on your own machine with a paper, an ORCID iD or a short
  description, and see which distant fields work on the same problem.
  Nothing leaves your machine unless you choose to share it.

Clients follow one [protocol](PROTOCOL.md). Two collect the map now: the
[Python client](clients/python/README.md), and the [Aether client](clients/aether/README.md),
a single program written in [Aether](https://github.com/aether-lang-dev/aether)
that needs no Python. On the same unit they write the same file, byte
for byte. How the pieces fit together, and in what order they are built, is
in [DESIGN.md](DESIGN.md).

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

## Reproduce, reuse, contribute

- Rerun the backtest: [research/README.md](research/README.md).
- Use the data in any language: one table per freeze, one row per pair of
  topics, in the [backtest release](https://github.com/nicolas-maman/undiscovered/releases),
  with every column explained in [docs/DATA.md](docs/DATA.md).
- Write a client in your own language: [docs/WRITE-A-CLIENT.md](docs/WRITE-A-CLIENT.md).
- Everything else: [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Code: [MIT](LICENSE). Data published by the project: [CC0](DATA_LICENSE.md),
derived from OpenAlex, which is also CC0.
