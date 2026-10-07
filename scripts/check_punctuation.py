"""Fail if any project text contains an em dash or an en dash.

The project writes in plain sentences: commas, colons, parentheses and full
stops, and "to" for ranges such as 2018 to 2023. The characters are named by
their code points here (chr) so that this file passes its own check.
"""

import pathlib
import sys

DASHES = (chr(0x2014), chr(0x2013))  # em dash, en dash
SUFFIXES = {".md", ".py", ".html", ".yml", ".yaml", ".json", ".cff", ".txt", ".ae", ".toml"}
SKIP = {".git", ".venv", "data", "cache", "__pycache__"}

bad = []
for path in pathlib.Path(".").rglob("*"):
    if not path.is_file() or path.suffix not in SUFFIXES or SKIP & set(path.parts):
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for number, line in enumerate(text.splitlines(), 1):
        if any(d in line for d in DASHES):
            bad.append(f"{path}:{number}: {line.strip()[:100]}")

if bad:
    print("Em or en dashes found; rewrite these lines in plain punctuation:")
    print("\n".join(bad))
    sys.exit(1)
print("ok")
