"""Distill units: what each paper works on and how, without its field's words.

For each work the client reads its title and abstract from OpenAlex and asks
the volunteer's model for two plain sentences: the problem and the approach.
Before anything is sent, every answer is checked the way the checking job
will check it: one JSON object, both parts present and short, at most
`max_avoided` of the paper's own distinctive words (the unit's `avoid` list)
reused, and not the same as the description of another paper in the unit. A
model that fails a check is asked once more, told why.

"The same as another paper" is measured on content words: two descriptions
whose counts of non-stop words have a cosine above SAME_SHAPE say the same
thing, whatever small words differ, so a model that fills one template for
every paper is caught paper by paper rather than after the whole unit.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter

from .models import Model
from .openalex import OpenAlex, abstract_text
from .stopwords import ENGLISH_STOP_WORDS

PROMPT = 1          # changes whenever SYSTEM, FORMAT or prompt() changes
MAX_WORDS = 60      # per part
SAME_SHAPE = 0.8    # cosine of content-word counts above which two descriptions say the same thing

SYSTEM = ("You help researchers in one field recognise work from another. You describe what a "
          "piece of research does in plain words that any scientist would understand.")

FORMAT = ('Answer with one JSON object and nothing else, in this form:\n'
          '{"problem": "...", "approach": "..."}\n'
          f'Each value is one or two sentences of plain English, at most {MAX_WORDS} words.')

WORD = re.compile(r"[^\W\d_]+")
THINKING = re.compile(r"<think>.*?</think>", re.S | re.I)


class Unusable(ValueError):
    """The model's answer cannot be used; the message says why, in words the model is shown."""


def fetch_works(api: OpenAlex, ids: list[str]) -> dict[str, dict]:
    """Title and abstract of each work, in one request."""
    data = api.get("works", {"filter": "openalex:" + "|".join(ids), "per_page": len(ids),
                             "select": "id,title,abstract_inverted_index"})
    out = {}
    for w in data.get("results", []):
        wid = w["id"].rsplit("/", 1)[-1]
        out[wid] = {"title": (w.get("title") or "").strip(),
                    "abstract": abstract_text(w.get("abstract_inverted_index"))}
    return out


def prompt(instructions: str, title: str, abstract: str, avoid: list[str]) -> str:
    parts = [instructions, f"Title: {title}", f"Abstract: {abstract}"]
    if avoid:
        parts.append("Do not use these words, which are specific to this paper: " + ", ".join(avoid) + ".")
    parts.append(FORMAT)
    return "\n\n".join(parts)


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def avoided(text: str, avoid: list[str]) -> list[str]:
    """Which of the avoid words appear in the text (case and a final s ignored)."""
    words = {_stem(w) for w in WORD.findall(text.lower())}
    return [a for a in avoid if _stem(a.lower()) in words]


def parse(answer: str) -> dict[str, str]:
    """The problem and approach from a model's answer, which may wrap the JSON in other text."""
    text = THINKING.sub("", answer)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise Unusable("the answer was not a JSON object")
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        raise Unusable("the answer was not valid JSON") from None
    out = {}
    for part in ("problem", "approach"):
        v = obj.get(part) if isinstance(obj, dict) else None
        if not isinstance(v, str) or len(v.split()) < 4:
            raise Unusable(f'"{part}" was missing or too short')
        out[part] = " ".join(v.split())
    return out


def model_name(model: dict) -> str:
    """A model as units and results name it: its id and the kind of endpoint that served it."""
    return f"{model['id']} ({model['provider']})"


def fingerprint(desc: dict[str, str]) -> str:
    """A description's words, lower case, in order: two descriptions with the same are the same."""
    return " ".join(WORD.findall((desc["problem"] + " " + desc["approach"]).lower()))


def _content(text: str) -> Counter:
    return Counter(w for w in WORD.findall(text.lower()) if w not in ENGLISH_STOP_WORDS)


def likeness(a: str, b: str) -> float:
    """Cosine between the content-word counts of two texts (descriptions or their fingerprints)."""
    ca, cb = _content(a), _content(b)
    dot = sum(n * cb[w] for w, n in ca.items())
    return dot / math.sqrt(sum(n * n for n in ca.values()) * sum(n * n for n in cb.values())) if dot else 0.0


def check(desc: dict[str, str], avoid: list[str], max_avoided: int, taken: set[str] = frozenset()) -> None:
    mine = fingerprint(desc)
    if any(likeness(mine, other) > SAME_SHAPE for other in sorted(taken)):
        raise Unusable("it said almost the same as the description of another paper in this unit")
    for part in ("problem", "approach"):
        if len(desc[part].split()) > MAX_WORDS:
            raise Unusable(f'"{part}" was longer than {MAX_WORDS} words')
    used = avoided(desc["problem"] + " " + desc["approach"], avoid)
    if len(used) > max_avoided:
        raise Unusable("it used words specific to the paper: " + ", ".join(used))


def describe(model: Model, instructions: str, work: dict, avoid: list[str], max_avoided: int,
             taken: set[str] = frozenset()) -> dict:
    """One work's description, checked. Raises Unusable after two failed attempts."""
    ask = prompt(instructions, work["title"], work["abstract"], avoid)
    reason = ""
    for _ in range(2):
        try:
            desc = parse(model.ask(SYSTEM, ask if not reason else
                                   f"{ask}\n\nYour previous answer could not be used: {reason}. Try again."))
            check(desc, avoid, max_avoided, taken)
            return desc
        except Unusable as e:
            reason = str(e)
    raise Unusable(reason)


def distill_unit(api: OpenAlex, model: Model, unit: dict, progress=lambda done, total: None) -> list[dict]:
    """The unit's descriptions, in its order.

    A work without an abstract in OpenAlex, or whose two answers both failed
    the checks, is left out. If the model fails on more than a quarter of the
    works, the unit is not submitted at all: the model is not up to the job.
    """
    works = fetch_works(api, unit["works"])
    avoid = unit.get("avoid", {})
    out, failed, last, taken = [], [], "", set()
    for i, wid in enumerate(unit["works"]):
        w = works.get(wid)
        if w and w["abstract"]:
            try:
                desc = describe(model, unit["instructions"], w, avoid.get(wid, []), unit.get("max_avoided", 2), taken)
                taken.add(fingerprint(desc))
                out.append({"work": wid, **desc})
            except Unusable as e:
                failed.append(wid)
                last = str(e)
        progress(i + 1, len(unit["works"]))
    if len(failed) * 4 > len(unit["works"]):
        raise Unusable(f"the model's answers failed the checks for {len(failed)} of {len(unit['works'])} "
                       f"papers (last: {last}); a larger model may do better")
    return out
