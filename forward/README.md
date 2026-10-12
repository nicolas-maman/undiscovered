# The forward test's ranking

Pairs of research topics from different domains, ranked at the end of 2025
by the first test's network model, before any of the citations that will
score them existed. The plan, registered before this ranking was computed,
is [research/FORWARD-TEST.md](../research/FORWARD-TEST.md).

| File | What it holds |
|---|---|
| `ranking-2025.csv` | the 26,475 eligible pairs, ranked by the network model, with both models' scores |
| `model.json` | both models in full: features, coefficients, intercept, and the means and scales they were fitted with |
| `records-2025.jsonl` | the 300 topic records at the end of 2025 the ranking was computed from (OpenAlex, CC0) |
| `SHA256SUMS` | the SHA-256 checksum of each of those three files |
| `SHA256SUMS.ots` | an OpenTimestamps proof that `SHA256SUMS` existed when it was stamped |

## Checking it

The files have not changed since they were stamped if their checksums
match:

```bash
sha256sum -c SHA256SUMS
```

and the proof shows when they were stamped, anchored in the Bitcoin
blockchain, without trusting this project or GitHub. With the standard
client (`pip install opentimestamps-client`):

```bash
ots upgrade SHA256SUMS.ots    # fetches the Bitcoin attestation once it exists
ots verify SHA256SUMS.ots
```

To score a pair without our code, apply `model.json` to its features: the
score is `1 / (1 + exp(-(intercept + sum(coef[i] * (x[i] - mean[i]) / scale[i]))))`.
The features are those of the first test, computed from the records by
`research/undiscovered_research/forward.py`.

## How it was made

`python -m undiscovered_research.forward rank --out forward`, from code
committed before the plan was registered, on 12 October 2026. Both models
were refitted from the first test's 2011 records and matched the published
coefficients exactly. The proof was made with `scripts/timestamp.py`, which
does what `ots stamp` does with the core OpenTimestamps library.

These files never change. The yearly counts that score them will be
published next to them, from 2027.
