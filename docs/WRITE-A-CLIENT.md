# Writing your own client

Any program that follows [PROTOCOL.md](../PROTOCOL.md) is a full client, in
any language. The project's own clients are in Python
([clients/python](../clients/python)) and, next, Aether. This page is the
whole recipe for the one kind of unit open now, `map`, with the exact
OpenAlex queries, so that your records match everyone else's.

## 1. Pick a unit

Read <https://raw.githubusercontent.com/nicolas-maman/undiscovered/map-2025/units/index.json>
and choose, at random, a unit whose `status` is `open` or `check` and that
you have not done before. Choosing at random keeps volunteers from
colliding without any server.

## 2. Fetch each topic's record

For a topic `T` and the unit's freeze year `F`, with the train window
`[F-7, F]` and the recent window `[F-2, F]`. All requests go to
`https://api.openalex.org`; add `api_key=<key>` if the volunteer has one.
Keep to at most 5 requests a second, and stop when OpenAlex answers 429
with "budget" in the body (the allowance resets at midnight UTC).

1. **Reference papers.** `GET /works` with
   `filter=primary_topic.id:T,publication_year:<F+1`,
   `sort=cited_by_count:desc`, `per_page=200`,
   `select=id,cited_by_count,counts_by_year`, two pages (cursor paging), so
   the 400 most cited works today. For each, citations up to the freeze are
   `cited_by_count` minus the `cited_by_count` of every `counts_by_year`
   entry whose year is after `F`. Sort by that, highest first, ties by work
   ID, and keep the first 100 whose count is above zero.
2. **Works per year.** `GET /works` with
   `filter=primary_topic.id:T,publication_year:F-7-F`,
   `group_by=publication_year`. `size` is their sum.
3. **Usable abstracts.** `GET /works` with
   `filter=primary_topic.id:T,publication_year:F-7-F,has_abstract:true`,
   `sample=40`, `seed=17`, `per_page=40`,
   `select=id,title,abstract_inverted_index`. Rebuild each abstract from
   its inverted index and join it to the title as `title + ". " + abstract`.
   A text is usable if it has at least 40 words (runs of letters) and at
   least a quarter of them are in scikit-learn's English stop-word list
   (copied in [clients/python/undiscovered/stopwords.py](../clients/python/undiscovered/stopwords.py)).
   `usable_abstracts` is how many of the texts are usable.
4. **Citing topics.** Three times, for the train window, the recent window
   and every year before the train window (`publication_year:<F-7`):
   `GET /works` with
   `filter=referenced_works:W1|W2|...|W100,publication_year:...`
   (the reference papers joined by `|`), `group_by=primary_topic.id`,
   `per_page=200`, cursor-paged until a page has fewer than 200 groups.
   Keep every group except `unknown`, as topic ID to count.

The record's fields and types are in
[schemas/map-record.schema.json](../schemas/map-record.schema.json), and
what they mean is in [DATA.md](DATA.md).

## 3. Check before you submit

Save the unit's result as one JSON file:

```json
{"unit": "u-000241", "freeze": 2025, "records": [ ...one record per topic, in the unit's order... ]}
```

and run the project's own checks on it:

```bash
python pipeline/intake.py --check my-result.json u-000241
```

It applies exactly what the intake job will, and says why a result would
be rejected.

## 4. Submit

1. Put the file in a secret gist under your GitHub account, as its only
   file.
2. Open an issue on `nicolas-maman/undiscovered` titled
   `map result u-000241` whose body has one fenced JSON block:

```json
{"unit": "u-000241", "protocol": 0, "client": {"name": "my-client", "version": "0.1.0"},
 "gist": "https://gist.github.com/<you>/<gist id>", "sha256": "<SHA-256 of the file's exact bytes>"}
```

The intake job replies on the issue within a few minutes and closes it.

## Good manners

- Run below normal priority and on part of the processor only; volunteers'
  computers are theirs first.
- Delete downloaded responses when a unit is done.
- Keep keys in the volunteer's own settings, never in a result, a URL you
  log, or a file you share.
