# The undiscovered client (Python)

Lend your computer to [undiscovered](https://nicolas-maman.github.io/undiscovered/).
Right now that means mapping which fields of science cite each other: your
computer asks OpenAlex, the free index of scholarly works, about ten topics
at a time, and submits what it finds. No AI model is needed for this. How
the pieces fit together is in [DESIGN.md](../../DESIGN.md).

## Before you start

- Python 3.10 or newer.
- A GitHub account, and the [GitHub command-line tool](https://cli.github.com)
  logged in once with `gh auth login`. Results are submitted from your
  account, so anyone can see who did what.
- Optional: a free OpenAlex key from <https://openalex.org/settings/api>.
  Without one you get about 1,000 calls a day; with one, about 10,000. A
  unit of ten topics takes about 250.

## Install and run

```bash
pip install "undiscovered @ git+https://github.com/nicolas-maman/undiscovered#subdirectory=clients/python"
undiscovered setup            # three questions, once
undiscovered work             # one unit, about three minutes
undiscovered work --units 20  # twenty, one after another
```

`undiscovered work --dry-run` does one unit and saves the result in the
current folder instead of submitting it, if you want to see what is sent.

## What it does on your computer

- It runs below normal priority, so whatever you are doing comes first.
- It keeps its downloads in a temporary folder and deletes it when each
  unit is done.
- It stops cleanly when your OpenAlex allowance for the day is spent.
  Running the same command the next day carries on.
- Your keys stay in your own settings file (`undiscovered setup` prints
  where). The OpenAlex key is sent only to OpenAlex, and your GitHub login
  only to GitHub.

## What it sends

For each unit, one secret gist under your GitHub account with the ten
topic records (about 300 KB), and one issue on the project naming the gist
and its checksum. A job on the project checks every record before using it,
and gives one unit in twenty to a second volunteer to compare.
