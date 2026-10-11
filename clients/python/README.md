# The undiscovered client (Python)

Lend your computer, and the AI model of your choice, to
[undiscovered](https://nicolas-maman.github.io/undiscovered/). There are two
jobs:

- **Describing papers** (needs a model). Your model reads a paper's title
  and abstract and writes, in two plain sentences, the problem it works on
  and how, without its field's words. Fields often name the same problem
  differently; descriptions without the jargon let papers on the same
  problem in different fields find each other. This is the job that needs
  many people: one model call per paper, tens of thousands of papers.
- **Mapping citations** (no model). Your computer asks OpenAlex, the free
  index of scholarly works, which fields cite which, ten topics at a time.

With a model set up, `undiscovered work` describes papers; without one, it
maps. How the pieces fit together is in [DESIGN.md](../../DESIGN.md).

## Before you start

- Python 3.10 or newer.
- A GitHub account, and the [GitHub command-line tool](https://cli.github.com)
  logged in once with `gh auth login`. Results are submitted from your
  account, so anyone can see who did what.
- A model, for describing. Any model works, and
  [docs/MODELS.md](../../docs/MODELS.md) compares the options:
  - one on your own computer, free and private: Ollama, LM Studio,
    llama.cpp, vLLM or Jan; `undiscovered setup` finds them by itself;
  - a free service in the cloud, with no graphics card needed: GitHub
    Models (with your GitHub account), Google Gemini, Groq, OpenRouter's
    free models or Mistral's free plan;
  - any service you already pay for: OpenAI, Anthropic, or anything else
    that speaks the OpenAI API. Their usage is billed to you, by them; the
    project pays for nothing and asks for nothing.
- Optional: a free OpenAlex key from <https://openalex.org/settings/api>.
  Without one you get about 1,000 calls a day; with one, about 10,000.
  Describing uses one call per twenty papers; mapping, about 250 per unit.

## Install and run

```bash
pip install "undiscovered @ git+https://github.com/nicolas-maman/undiscovered#subdirectory=clients/python"
undiscovered setup            # three questions, once
undiscovered work             # one unit
undiscovered work --units 20  # twenty, one after another
undiscovered work --kind map  # map units, even with a model set up
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
  where). The model key is sent only to your model's server, the OpenAlex
  key only to OpenAlex, and your GitHub login only to GitHub.

## What it sends, and to whom

- To your model: each paper's title and abstract, which are public, and the
  instructions. Nothing about you.
- To the project, for a describing unit: one issue under your GitHub
  account with the descriptions, the name of the model that wrote them and
  the client's version. Every description is checked before it counts: two
  short parts, and no more than two of the paper's own distinctive words,
  which the unit lists and the model is told to avoid. The client runs the
  same checks first and asks the model again once if an answer fails, so
  nothing that would be turned away is sent. Each unit is described by two
  volunteers, so descriptions from different models can be compared.
- To the project, for a map unit: one secret gist under your GitHub account
  with the ten topic records (about 300 KB), and one issue naming the gist
  and its checksum. A job on the project checks every record before using
  it, and gives one unit in twenty to a second volunteer to compare.
