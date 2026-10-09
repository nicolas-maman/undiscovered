# Contributing

Thank you. There are four ways in, from least to most code.

1. **Find a flaw.** Open an issue with the
   [plan-review form](https://github.com/nicolas-maman/undiscovered/issues/new?template=plan-review.yml)
   if anything in the [analysis plan](research/PREREGISTRATION.md), the
   [results](https://nicolas-maman.github.io/undiscovered/results.html) or
   [DESIGN.md](DESIGN.md) could make a conclusion wrong.
2. **Lend your computer.** Run a client: [Python](clients/python/README.md) or [Aether](clients/aether/README.md).
3. **Write a client** in your own language: [docs/WRITE-A-CLIENT.md](docs/WRITE-A-CLIENT.md).
4. **Change the code.** Open a pull request.

## Working on the code

```bash
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r research/requirements.txt
pip install -e clients/python
python -m pytest -q research          # the analysis
python -m pytest -q clients/python/tests pipeline/tests
python scripts/check_punctuation.py
```

The Aether client builds and tests on its own, with the Aether toolchain
(`ae`, 0.782 or newer): from `clients/aether`, `ae build src/main.ae -o undiscovered`
and `ae test tests/test_client.ae`.

All tests run offline. CI runs the same, plus a check that every OpenAlex ID
in PROTOCOL.md exists.

## Rules the project keeps

- **The plan comes first.** Nothing about an analysis changes after its
  outcomes have been seen, except as a dated *deviation* in its plan. A new
  question gets a new plan, written before its data is collected.
- **Every number traces to code.** Published results name the commit that
  produced them, and are only published from committed code.
- **Gentle on the computer it runs on:** below normal priority, at most half
  the processor, caches deleted when done.
- **Plain words.** Say what was done and what it showed, with the
  uncertainty. No hype. Project text uses no em or en dashes (a check
  enforces this).
- **Data is CC0, code is MIT.**
