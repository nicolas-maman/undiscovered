# Describing data, 2025

This branch holds data, not code. The code is on `main`.

- `units/index.json`: 421 units (all of twenty papers but u-100403, of nine, and u-100421, of sixteen), each unit's status
  (`open`, `check` when it still needs a second model, or `done`), the
  models and results it has had, each paper's distinctive words, and the
  rule that chose them.
- `papers.json`: each paper's topic (id and name), subfield, field and domain. The papers are the sampled
  works of the first test's 300 topics, up to 2025, that are research and
  have a usable abstract (8,049), and the 86 benchmark papers of
  `known-twins.json`.
- `abstracts.jsonl`: each paper's title, year and abstract, from OpenAlex
  (CC0), one paper per line, for the site's map and search and for the
  checking job's test that descriptions match their papers
  (`pipeline/abstracts.py`).
- `results/<unit>/<issue>.json`: every accepted result, whole: who sent it,
  with which client and which model, how many of its descriptions found
  their own paper's abstract, and its descriptions.
- `rejected/<issue>.json`: every result the checking job turned away, with
  its reason; `rejected/index.json` lists the latest for the site.
- `progress.json`: the counts the site shows.
- `known-twins.json`: the papers of a published benchmark of cross-field twins
  (Kulikowski 2026, CC BY 4.0) that units u-100404 to u-100421 hold among
  ordinary papers, with their families, for the test in
  [research/KNOWN-TWINS.md](https://github.com/nicolas-maman/undiscovered/blob/main/research/KNOWN-TWINS.md).
- `combined/`: rebuilt after every accepted result by `pipeline/combine.py`:
  `descriptions.jsonl`, the open index, one paper per line; `models.json`,
  how well each model's descriptions agree with other models' descriptions
  of the same papers, against chance; `twins.json`, the most alike pairs of
  papers from different fields, with the words that made them, their fields'
  distance and whether they already cite each other; `neighbours.json`,
  each described paper's nearest papers in other fields; and `map.json`,
  every paper placed by its abstract and by its descriptions
  (`pipeline/maps.py`).

The `intake` workflow on `main` writes here when it accepts a result. The
units were made by `pipeline/distill_units.py`; what a unit and a result
hold is in
[PROTOCOL.md](https://github.com/nicolas-maman/undiscovered/blob/main/PROTOCOL.md#work-units),
and how to take part, with any model, in
[docs/MODELS.md](https://github.com/nicolas-maman/undiscovered/blob/main/docs/MODELS.md).
Data published under CC0. The titles and abstracts come from OpenAlex, which
is also CC0; volunteers' clients still read each unit's abstracts from
OpenAlex themselves.
