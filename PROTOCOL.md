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

Two kinds:

| kind | input | the volunteer returns |
|---|---|---|
| `rank` | one topic and up to 50 candidate topics from other domains | the candidates ranked, and for the top 3 an evidence pair of works |
| `judge` | one candidate bridge with its evidence pair | a verdict (`real`, `superficial`, `unclear`) and a one-paragraph reason |

A client fetches what it needs from OpenAlex itself (titles and abstracts of
the topics' papers), so the fetching is spread across volunteers and their
own OpenAlex budgets.

Some units are **gold units**: their answer is already known (from the
backtest: pairs that did or did not connect later). They look exactly like
other units. They measure how good each contributor's model is.

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
    {"candidate": "T11478", "works": ["W2741809807", "W2963403868"], "why": "…"}
  ]
}
```

For `judge` units, `ranking` is replaced by `"verdict"` and `"reason"`.

## Ratings

From the `rating` form, by anyone, about any published bridge:

```json
{"bridge": "b-T10014-T12108", "rating": 4, "expertise": "own-field", "comment": "…"}
```

`rating` is 1–5 (1 = no real connection, 5 = I would start a project on
this). `expertise` is `own-field`, `adjacent` or `outside`. Ratings by people
working in one of the two fields count most.

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
