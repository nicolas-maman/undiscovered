# The undiscovered client (Aether)

The same volunteer client as [clients/python](../python), written in
[Aether](https://github.com/aether-lang-dev/aether). It compiles to one
native program: once built, it is a single file to copy and run, with no
Python or packages to install. There is no prebuilt download yet.

It does the same two jobs:

- **Describing papers** (needs an AI model). Your model reads a paper's
  title and abstract and writes, in two plain sentences, the problem it
  works on and how, without its field's words.
- **Mapping citations** (no model). Your computer asks OpenAlex which fields
  cite which, ten topics at a time.

With a model set up, `undiscovered work` describes papers; without one, it
maps.

It has the same commands, reads and writes the same settings file, and
produces the same results. On map unit u-000300 its result file was byte
for byte the Python client's. On describing unit u-100076, with the same
stand-in model, its result file was the Python client's byte for byte but
for the client's name, and the checking job accepted it.

## Build

You need the Aether toolchain (`ae`, version 0.782 or newer) and the C
compiler it uses. From this folder:

```bash
ae build src/main.ae -o undiscovered
```

On Windows, `ae` links OpenSSL from MSYS2's UCRT64 environment, so that
environment's gcc has to come first on the PATH (PowerShell):

```powershell
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
ae build src/main.ae -o undiscovered
```

The result, `undiscovered.exe`, needs only Windows' own DLLs. The offline
tests run with `ae test tests/test_client.ae` and
`ae test tests/test_distill.ae` (one file per call: `ae test` runs only one
of the files it is given, [aether#2752](https://github.com/aether-lang-dev/aether/issues/2752)).

## Run

What you need is the same as for the Python client: a GitHub account with
the [GitHub command-line tool](https://cli.github.com) logged in once
(`gh auth login`), or a token in `GITHUB_TOKEN`; optionally a free OpenAlex
key from <https://openalex.org/settings/api>; and, for describing, a model
([docs/MODELS.md](../../docs/MODELS.md) compares the options).

```bash
undiscovered setup            # three questions, once
undiscovered work             # one unit
undiscovered work --units 20  # twenty, one after another
undiscovered work --dry-run   # one unit, saved here instead of submitted
undiscovered work --unit u-000241 --dry-run   # a given unit
undiscovered work --kind map  # map units, even with a model set up
undiscovered --version
```

`setup` offers the models of any server running on this machine (Ollama,
LM Studio, llama.cpp, vLLM, Jan, on their usual ports), then the services
the Python client offers by name, then any other server that speaks the
OpenAI API. Each model setting can also come from the environment, which
takes precedence over the settings file:

| Variable | What it sets |
|---|---|
| `UNDISCOVERED_MODEL_PROVIDER` | `openai-compatible` (the default), `anthropic` or `google` |
| `UNDISCOVERED_MODEL_BASE_URL` | the server's address, such as `http://127.0.0.1:11434/v1` |
| `UNDISCOVERED_MODEL` | the model's name, as the server writes it |
| `UNDISCOVERED_MODEL_KEY` | the key, if the server needs one |

On Windows, Aether's HTTPS does not read the Windows certificate store yet
([aether#2675](https://github.com/aether-lang-dev/aether/issues/2675)).
It needs a certificate bundle file, and its two HTTPS stacks (one for
OpenAlex, the other for GitHub, the list of units and a model's server)
look for one in different places, so point `SSL_CERT_FILE` at a bundle
before running it, for example the one Git for Windows installs:

```powershell
$env:SSL_CERT_FILE = "C:\Program Files\Git\mingw64\etc\ssl\certs\ca-bundle.crt"
```

A model server on this machine is reached over plain `http://` and needs no
bundle.

## What it does on your computer

- It runs below normal priority (below-normal priority class on Windows,
  `nice 10` elsewhere), so whatever you are doing comes first.
- It keeps nothing on disk while it works. `--dry-run` writes one file, the
  result, in the current folder: `undiscovered-<unit>.md` for describing,
  `undiscovered-<unit>.json` for mapping.
- It stops cleanly when your OpenAlex allowance for the day is spent, and on
  Ctrl-C; nothing half-done is ever submitted. A model whose answers fail
  the checks on more than a quarter of a unit's papers stops the unit, and
  nothing is sent.
- It asks every question at temperature 0. When a model's server says it is
  asked too fast, the client waits as long as the server says and asks more
  slowly from then on.
- Your settings are in the same file the Python client uses:
  `%APPDATA%\undiscovered\config.json` on Windows,
  `~/.config/undiscovered/config.json` elsewhere. The OpenAlex key comes from
  `OPENALEX_API_KEY` or that file, is sent only to OpenAlex as the `api_key`
  parameter, and is never printed. The model's key is sent only to the
  model's server, and the GitHub token only to GitHub; neither is printed.

## How it stays the same as the Python client

- Whether an abstract is usable, and whether a description reuses a paper's
  own words, depend on how Python's `re` and `str` see text: which code
  points are letters, what `str.lower` makes of each (final sigma
  included), what `str.split` calls space. `tools/gen_tables.py` writes
  Python's answers into `src/letters.ae` and `src/casing.ae`, and the
  stop-word list into `src/stopwords.ae`. Run it again (with the Python the
  reference client uses) if any of them changes.
- Whether a model's answer is valid JSON decides whether the model is asked
  again and why, so `src/pyjson.ae` reads answers as Python's `json.loads`
  does, which `std.json` does not quite (Python takes `NaN`, unpaired
  surrogate escapes, and the last of two members with the same name).
- `tests/test_client.ae` and `tests/test_distill.ae` hold the Python
  client's offline tests, plus the texts that must come out byte for byte
  as Python writes them: the issue bodies, the GitHub and model requests,
  the result files, and what Python makes of awkward answers and words.
- The OpenAlex requests go over Aether's own TLS 1.3 client instead of
  `std.http.client`, which cuts request paths at 1,023 bytes
  ([aether#2674](https://github.com/aether-lang-dev/aether/issues/2674)); the
  citing-topic queries name 100 works and run to about 1,500. Model requests
  are POSTs with short paths and use `std.http.client`.

Where it still differs: a `Retry-After` date is read only in the form HTTP
servers send (`Wed, 21 Oct 2015 07:28:00 GMT`), and a model server it cannot
reach is reported with Aether's error text rather than Python's exception
name. On Windows, Python turns each line end it prints into `\r\n` when its
output goes to a file; this client writes `\n`. The result file is written
as Python writes it, with `\r\n` on Windows.

On Linux, CI builds the client and runs its offline tests on every change;
the client itself has not yet been run there, or on macOS, against real
servers.

## Files

| File | What it holds |
|---|---|
| `src/main.ae` | the command line |
| `src/work.ae` | `setup` and `work`: picking units, doing them, submitting |
| `src/distill.ae` | describing a unit's papers, and the checks every description passes (docs/WRITE-A-CLIENT.md) |
| `src/models.ae` | the model's server: the three kinds of endpoint, pacing, retries |
| `src/mapper.ae` | one topic's record, query by query (docs/WRITE-A-CLIENT.md) |
| `src/openalex.ae` | OpenAlex requests: pacing, retries, the daily allowance |
| `src/english.ae` | counting words and stop words in an abstract |
| `src/pytext.ae` | Python's `str.lower`, `str.split`, `str.strip` and word pattern |
| `src/pyjson.ae` | reading a model's answer as Python's `json.loads` does |
| `src/letters.ae`, `src/casing.ae`, `src/stopwords.ae` | generated tables (tools/gen_tables.py) |
| `src/jsontext.ae` | reading JSON leniently, writing it as Python does |
| `src/settings.ae`, `src/github.ae`, `src/gentle.ae`, `src/secret.ae`, `src/version.ae` | settings, GitHub, priority, hidden input, name and version |
