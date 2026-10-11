# Describing data, 2025

This branch holds data, not code. The code is on `main`.

- `units/index.json`: 403 units of twenty papers, each unit's status
  (`open`, `check` when it still needs a second volunteer, or `done`), each
  paper's distinctive words, and the rule that chose them.
- `papers.json`: each paper's topic (id and name), subfield, field and domain. The papers are the sampled
  works of the first test's 300 topics, up to 2025, that are research and
  have a usable abstract: 8,049 in all.
- `results/<unit>/<issue>.json`: every accepted result, whole: who sent it,
  with which client and which model, and its descriptions.

The `intake` workflow on `main` writes here when it accepts a result. The
units were made by `pipeline/distill_units.py`; what a unit and a result
hold is in
[PROTOCOL.md](https://github.com/nicolas-maman/undiscovered/blob/main/PROTOCOL.md#work-units),
and how to take part, with any model, in
[docs/MODELS.md](https://github.com/nicolas-maman/undiscovered/blob/main/docs/MODELS.md).
Data published under CC0. The titles and abstracts are not copied here: each
client reads them from OpenAlex, which is also CC0.
