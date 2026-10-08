# The undiscovered protocol (v0, draft)

How clients, volunteers and the site exchange work. Language-neutral on
purpose: the Python and Aether clients implement exactly this, and any other
client that does is a full participant. JSON Schemas for every message are in
[`schemas/`](schemas/).

> v0 is a draft. It will change until the backtest milestone is done; the
> version number moves to 1 when a client is published against it.

## Principles

1. **No server.** Work units are static files on the project site; results,
   ratings and reports arrive as GitHub Issues through issue forms; GitHub
   Actions validate and aggregate them. Nothing to host, nothing to pay for.
2. **Any model.** The protocol never names a model. Every result says which
   one produced it (provenance), and the network learns how far to trust it.
3. **Comparable whatever the model.** Volunteers return verdicts, rankings and
   evidence paper IDs, never raw scores meant to be compared across models.
   Every paper ID is checked against OpenAlex.
4. **Keys stay home.** Provider keys and OpenAlex keys live on the
   contributor's machine. A result never contains one; the validator rejects
   any submission that looks like it does.

## Identifiers

- Topics, works and authors use OpenAlex short IDs: `T10005`, `W2741809807`,
  `A5023888391`.
- A unit is `u-` followed by 6 digits. A bridge is `b-` followed by the two
  topic IDs in sorted order: `b-T10014-T12108`.

## Work units

Published at `https://<site>/data/units/<unit>.json`, with an index at
`/data/units/index.json` listing every open unit and how many accepted results
it has.

```json
{
  "unit": "u-000123",
  "protocol": 0,
  "kind": "rank",
  "topic": "T10014",
  "candidates": ["T12108", "T11478", "T10872"],
  "as_of": 2025,
  "instructions": "Rank the candidate topics by how likely their literature holds a method, finding or problem that the topic's researchers could use and do not yet cite. For the top three, give the strongest pair of papers (one from each side) as evidence.",
  "quorum": 2
}
```

Three kinds:

| kind | input | the volunteer returns |
|---|---|---|
| `distill` | up to 20 works | for each, the problem it works on and how, described without its field's vocabulary |
| `rank` | one topic and up to 50 candidate topics from other domains | the candidates ranked, and for the top 3 an evidence pair of works: one from the topic, one from the candidate |
| `judge` | one candidate bridge with its evidence pair | a verdict (`real`, `superficial`, `unclear`) and a one-paragraph reason |

`distill` comes first because it is the part that needs the most model
calls: one per paper, which no single project can afford across all of
science. Its output is an open index of field-free problem descriptions,
published under CC0. Fields often name the same problem differently, and
descriptions without the jargon are what let papers that solve the same
problem in different fields find each other (see Kulikowski, 2026, in the
README).

```json
{
  "unit": "u-000456",
  "protocol": 0,
  "kind": "distill",
  "works": ["W2028823348", "W2014952121"],
  "instructions": "For each work, read its title and abstract in OpenAlex. Describe the problem it works on and how it goes about it, so that a researcher in any field would recognise the problem. Do not name the field, its methods or its objects of study, and do not reuse terms from the abstract that only that field would use.",
  "quorum": 3
}
```

A client fetches what it needs from OpenAlex itself (titles and
abstracts), so the fetching is spread across volunteers and their own
OpenAlex budgets.

Some units are **gold units**: their answer is already known (from the
backtest: pairs that did or did not connect later). They look exactly like
other units. They measure how good each contributor's model is.

A limit worth stating: a language model trained on papers from after the
gold unit's date may simply remember whether the pair connected. Gold units
therefore measure how reliable a model is at this task, not whether it can
foresee anything. Any claim that the method foresees connections rests only
on tests that use no language model and nothing after their freeze date:
the backtest, and later the forward test described in
[research/NEXT.md](research/NEXT.md).

## Results

Submitted as an issue through the `work-result` form. The body is one fenced
JSON block:

```json
{
  "unit": "u-000123",
  "protocol": 0,
  "client": {"name": "undiscovered-py", "version": "0.1.0"},
  "model": {"provider": "openai-compatible", "id": "qwen2.5:14b", "embedding": "nomic-embed-text"},
  "ranking": ["T11478", "T12108", "T10872"],
  "evidence": [
    {"candidate": "T11478", "works": ["W2028823348", "W2014952121"], "why": "…"}
  ]
}
```

For `judge` units, `ranking` is replaced by `"verdict"` and `"reason"`. For
`distill` units it is replaced by `"descriptions"`, one per work:

```json
"descriptions": [
  {"work": "W2028823348",
   "problem": "Measure quickly and cheaply how much of one small molecule a living tissue has built up, used as a sign of how short of water it is.",
   "approach": "Extract the tissue, react the extract with a reagent that turns that molecule coloured, move the coloured product into a solvent, and read its colour against known amounts."},
  {"work": "W2014952121",
   "problem": "Deliver the same data to many users efficiently when what they want is the data itself, not a particular machine that holds it.",
   "approach": "Ask the network for data by a signed name instead of by location, so that any node holding a copy can answer, and let nodes keep copies of what passes through them."}
]
```

A `distill` result is checked in three ways before it counts:

- **No jargon.** For each work, the validator takes the terms in its title
  and abstract that are most specific to it compared with other papers. If
  more than a few of them reappear in the description, the description is
  rejected. The threshold is set on the first trial runs and published with
  the validator.
- **Agreement between models.** Descriptions of the same work from different
  contributors are compared by embedding. The accepted description is the
  one closest to the others, and a model whose descriptions keep landing
  far from the rest loses weight.
- **Known twins.** Some units contain pairs of works already known to solve
  the same problem in different fields, such as those in published
  benchmarks of cross-field twins, used where their licence allows. A
  model whose descriptions of known twins land far apart loses weight.

## Ratings

From the `rating` form, by anyone, about any published bridge:

```json
{"bridge": "b-T10014-T12108", "rating": 4, "expertise": "own-field", "comment": "…"}
```

`rating` is 1 to 5 (1 = no real connection, 5 = I would start a project on
this). `expertise` is `own-field`, `adjacent` or `outside`. Ratings by people
working in one of the two fields count most.

### Who is rating (planned, not in v0)

Work results need no identity: they are checked by OpenAlex lookups, known
answers and agreement between contributors. A rating is different, because
its weight depends on whether the rater really works in one of the two
fields, and the `expertise` field above is self-declared. The plan:

1. **Optional sign-in with ORCID.** ORCID supports OpenID Connect's implicit
   flow, so the static site can obtain an ORCID-signed ID token in the
   browser with no server. The token is short-lived (10 minutes) and can be
   checked against the keys ORCID publishes at `https://orcid.org/oauth/jwks`.
   It needs a free Public API client, which ORCID grants to anyone with an
   ORCID iD (Developer Tools on the record).
2. **The token never appears in public.** Issues on a public repository are
   public, and the token carries the person's name, so it must not go into
   the issue as it is. The site encrypts it in the browser with the
   project's public key; only the validating Action holds the private key,
   as a repository secret. Before sign-in, the site sets the OpenID nonce,
   which ORCID copies into the token, to a hash of the rating being
   submitted. The Action then checks the signature, that the nonce matches
   the rating in the issue, and that the issue was opened while the token
   was valid. A copied token cannot be reused for a different rating, and
   one person's ratings of the same pair count once.
3. **Expertise from the record, not the claim.** With a verified ORCID iD the
   Action looks the person up in OpenAlex (a single-record lookup, which
   costs nothing; the record lists the topics the person has published in)
   and checks whether either topic of the pair is among them. That decides
   `own-field`, whatever the form says.
4. **Anonymous ratings still count**, with a lower weight, so taking part
   never requires an account.

The published rating shows the ORCID iD only if the rater ticks a box to
show it; otherwise it shows only the weight it was given.

## Bridge reports

From the `bridge-report` form: a connection someone found, through `ask` or by
hand, with its evidence works. It enters the queue as a `judge` unit.

## Aggregation (GitHub Actions)

1. **Validate.** Schema, unit exists and is open, every work ID resolves in
   OpenAlex and belongs to the claimed topics, no secrets in the body. A
   failure is labelled `invalid` and closed with the reason.
2. **Weigh.** Each `(provider, model)` pair has an accuracy measured on gold
   units; weight is a smoothed log-odds of that accuracy, starting neutral.
   The model leaderboard on the site is this table.
3. **Accept.** A unit is accepted when results reach its quorum and agree by
   weighted majority. Agreement between different models counts for more than
   agreement between two runs of the same model.
4. **Publish.** Accepted results update `data/bridges.json`; the site is
   rebuilt; the issues are closed with a link to what they changed.

## Versioning

`protocol` is an integer in every message. A client refuses units with a
higher protocol than it knows; the validator accepts results for the current
and previous protocol.
