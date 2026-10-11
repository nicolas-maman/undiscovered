# Connecting a model

Describing papers needs an AI model, and any model will do: one on your own
computer, a free service in the cloud, or one you already pay for. The
project prescribes none and pays for none. Every result records which model
made it, and each unit is described by two volunteers, so models are compared
on the same papers and the results page will show which ones do this well.
Nobody knows yet which those are.

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
| [GitHub Models](https://github.com/marketplace/models) | a [GitHub token](https://github.com/settings/tokens) with the Models: read permission | free for personal accounts; model names include the publisher, as in its catalogue |
| [Google Gemini](https://ai.google.dev) | [AI Studio](https://aistudio.google.com/apikey) | free tier; the client uses Google's own API |
| [Groq](https://groq.com) | [console](https://console.groq.com/keys) | free tier |
| [OpenRouter](https://openrouter.ai) | [keys](https://openrouter.ai/keys) | models whose name ends in `:free` cost nothing, but only a small number of requests a day |
| [Mistral](https://mistral.ai) | [console](https://console.mistral.ai) | free Experiment plan; Mistral says it may use what it is sent on that plan to train its models |
| [Hugging Face](https://huggingface.co/docs/inference-providers) | [tokens](https://huggingface.co/settings/tokens), at `https://router.huggingface.co/v1` | a small free credit each month |

Choose GitHub Models, Gemini, Groq, OpenRouter or Mistral by name in
`undiscovered setup`; for Hugging Face, choose "another server" and give the
address in the table.

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
