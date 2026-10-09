# The undiscovered client (Aether)

The same volunteer client as [clients/python](../python), written in
[Aether](https://github.com/aether-lang-dev/aether). It compiles to one
native program: once built, it is a single file to copy and run, with no
Python or packages to install. There is no prebuilt download yet.

It has the same commands, reads and writes the same settings file, and
produces the same results: on unit u-000300 its result file was byte for byte
the Python client's.

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
tests run with `ae test tests/test_client.ae`.

## Run

What you need is the same as for the Python client: a GitHub account with
the [GitHub command-line tool](https://cli.github.com) logged in once
(`gh auth login`), or a token in `GITHUB_TOKEN`, and optionally a free
OpenAlex key from <https://openalex.org/settings/api>.

```bash
undiscovered setup            # three questions, once
undiscovered work             # one unit
undiscovered work --units 20  # twenty, one after another
undiscovered work --dry-run   # one unit, saved here instead of submitted
undiscovered work --unit u-000241 --dry-run   # a given unit
undiscovered --version
```

On Windows, Aether's HTTPS does not read the Windows certificate store yet.
It needs a certificate bundle file, and its two HTTPS stacks (one for
OpenAlex, one for GitHub) look for one in different places, so point
`SSL_CERT_FILE` at a bundle before running it, for example the one Git for
Windows installs:

```powershell
$env:SSL_CERT_FILE = "C:\Program Files\Git\mingw64\etc\ssl\certs\ca-bundle.crt"
```

## What it does on your computer

- It runs below normal priority (below-normal priority class on Windows,
  `nice 10` elsewhere), so whatever you are doing comes first.
- It keeps nothing on disk while it works. `--dry-run` writes one file, the
  result, in the current folder.
- It stops cleanly when your OpenAlex allowance for the day is spent, and on
  Ctrl-C; nothing half-done is ever submitted.
- Your settings are in the same file the Python client uses:
  `%APPDATA%\undiscovered\config.json` on Windows,
  `~/.config/undiscovered/config.json` elsewhere. The OpenAlex key comes from
  `OPENALEX_API_KEY` or that file, is sent only to OpenAlex as the `api_key`
  parameter, and is never printed. The GitHub token is sent only to GitHub.

## How it stays the same as the Python client

- Whether an abstract is usable depends on how Python's `re` and
  `str.lower` see letters. `tools/gen_tables.py` writes Python's answer into
  `src/letters.ae`, and the stop-word list into `src/stopwords.ae`. Run it
  again (with the Python the reference client uses) if either changes.
- `tests/test_client.ae` holds the Python client's offline tests, plus the
  texts that must come out byte for byte as Python writes them: the issue
  body, the GitHub requests, the result file.
- The OpenAlex requests go over Aether's own TLS 1.3 client instead of
  `std.http.client`, which cuts request paths at 1,023 bytes; the
  citing-topic queries name 100 works and run to about 1,500.

The non-Windows parts (priority, hidden input, settings path) compile but
have not been run on Linux or macOS yet.

## Files

| File | What it holds |
|---|---|
| `src/main.ae` | the command line |
| `src/work.ae` | `setup` and `work`: picking units, mapping them, submitting |
| `src/mapper.ae` | one topic's record, query by query (docs/WRITE-A-CLIENT.md) |
| `src/openalex.ae` | OpenAlex requests: pacing, retries, the daily allowance |
| `src/english.ae` | counting words and stop words in an abstract |
| `src/letters.ae`, `src/stopwords.ae` | generated tables (tools/gen_tables.py) |
| `src/jsontext.ae` | reading JSON leniently, writing it as Python does |
| `src/settings.ae`, `src/github.ae`, `src/gentle.ae`, `src/secret.ae`, `src/version.ae` | settings, GitHub, priority, hidden input, name and version |
