# Connecting a model

Describing papers needs an AI model, and any model will do: one on your own
computer, a free service in the cloud, or one you already pay for. The
project prescribes none and pays for none. Every result records which model
made it, and each unit is described by two different models, so models are
compared on the same papers and the
[explorer](https://nicolas-maman.github.io/undiscovered/explore.html#models)
shows how well each agrees with the others.

Two small open models running on a laptop (Qwen3 4B and Llama 3.2 3B, 4-bit,
on an Apple M1) passed every check on the first try for five units, at four
to five seconds a paper, and agreed with each other beyond chance on 84% of
the papers (October 2026). A model of that size is enough.

## In the browser: nothing to install

[Describe papers in your browser](https://nicolas-maman.github.io/undiscovered/describe.html)
runs a model in the page itself with [WebLLM](https://github.com/mlc-ai/web-llm)
(Qwen3 4B or Llama 3.2 3B; a one-time download of about 2.5 to 3.5 GB that
the browser keeps), in a recent Chrome, Edge or Safari with WebGPU. On an
Apple M1, Qwen3 4B described a whole unit in the page in four and a half
minutes, every paper passing the checks; Llama 3.2 3B took thirteen and a
half, and left out 3 of 20 papers whose answers were not valid JSON, still
enough to send. Qwen3 1.7B, tried too, reused the papers' own words on 13 of
20 papers and is not offered. The same
page also takes a key for any of the services below, or the address of a
server on your computer, and opens the GitHub form for the result.

## The command-line client

`undiscovered setup` asks which model to use and offers the options below.
To change it later, run `undiscovered setup` again.

## On your own computer: free and private

If one of these is running, `undiscovered setup` finds it and lists its
models; pick one by number.

| Server | Address the client uses |
|---|---|
| [Ollama](https://ollama.com) | `http://127.0.0.1:11434/v1` |
| [LM Studio](https://lmstudio.ai) (start its local server) | `http://127.0.0.1:1234/v1` |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` | `http://127.0.0.1:8080/v1` |
| [vLLM](https://docs.vllm.ai) | `http://127.0.0.1:8000/v1` |
| [Jan](https://jan.ai) | `http://127.0.0.1:1337/v1` |

A server on another port or another machine works too: choose "another
server that speaks the OpenAI API" and give its address.

## Free in the cloud: no graphics card needed

Each needs a free account and a key, and limits how many requests you may
make per minute or per day. The limits change, so the client does not
assume any: it waits as long as the server asks and slows down when told it
is asking too fast. A unit is twenty requests.

| Service | Key | Notes |
|---|---|---|
| [Google Gemini](https://ai.google.dev/gemini-api/docs/pricing) | [AI Studio](https://aistudio.google.com/apikey) | free tier for several models; Google says it uses what is sent on the free tier to improve its products. The client uses Google's own API |
| [Groq](https://console.groq.com/docs/rate-limits) | [console](https://console.groq.com/keys) | free plan |
| [OpenRouter](https://openrouter.ai/docs/api-reference/limits) | [keys](https://openrouter.ai/keys) | models whose name ends in `:free` cost nothing: 20 requests a minute and 50 a day, or 1,000 a day once the account has bought 10 credits |
| [Mistral](https://docs.mistral.ai/getting-started/quickstart/) | [console](https://console.mistral.ai) | free mode; read its terms on how it uses what it is sent |
| [Hugging Face](https://huggingface.co/docs/inference-providers/pricing) | [tokens](https://huggingface.co/settings/tokens), at `https://router.huggingface.co/v1` | a small free credit each month |

Choose Gemini, Groq, OpenRouter or Mistral by name in `undiscovered setup`;
for Hugging Face, choose "another server" and give the address in the
table. These were checked against each service's own pages on 11 October
2026. Free offers change: GitHub Models, for one, closed in July 2026. If
one stops working, tell us in an issue.

## Paid services

OpenAI and Anthropic are offered by name. Any other service that speaks
OpenAI's chat completions API works through "another server", for example:

| Service | Address |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| Together AI | `https://api.together.xyz/v1` |
| DeepSeek | `https://api.deepseek.com` |
| xAI | `https://api.x.ai/v1` |

Usage is billed to you, by them. A unit is twenty short requests, each with
one abstract in and two sentences out.

## Without the setup questions

For a notebook, a script or a server, the model can be given entirely
through environment variables, which take precedence over the settings file:

```bash
export UNDISCOVERED_MODEL_PROVIDER=openai-compatible   # or anthropic, or google
export UNDISCOVERED_MODEL_BASE_URL=http://127.0.0.1:11434/v1
export UNDISCOVERED_MODEL=<the model's name, as the server lists it>
export UNDISCOVERED_MODEL_KEY=<the key, if the server needs one>
undiscovered work --units 5
```

`OPENALEX_API_KEY` works the same way for the OpenAlex key. GitHub still
needs a login (`gh auth login`) or a `GITHUB_TOKEN`, because results are
submitted from your account.

## What is sent where

- To the model's server: each paper's title and abstract, which are public,
  and the instructions. Nothing about you. If a service's terms matter to
  you (some free plans train on what they receive), read them before you
  choose it.
- To the project: the descriptions and the name of the model that wrote
  them, in an issue under your GitHub account. Never a key.
- Keys stay in your settings file or your environment. Each is sent only to
  the service it belongs to.

## Writing your own client

The describing job is defined in [PROTOCOL.md](../PROTOCOL.md#work-units):
what a unit holds, what a result must contain, and the checks it must pass.
Any program that follows it, in any language and with any model, is a full
participant.
