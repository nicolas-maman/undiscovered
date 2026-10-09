# Map data, freeze 2025

This branch holds data, not code. The code is on `main`.

- `units/index.json`: every OpenAlex topic, ten to a unit, and each unit's
  status (`open`, `check` when a second volunteer is needed, `done`, or
  `disputed`).
- `records/<topic>.json`: the accepted citation record for each topic.
- `results/<unit>.json`: who submitted each accepted result, with the gist
  and checksum.

The `intake` workflow on `main` writes here when it accepts a result. See
[DESIGN.md](https://github.com/nicolas-maman/undiscovered/blob/main/DESIGN.md)
for how the map is made and used. Data published under CC0, derived from
OpenAlex, which is also CC0.
