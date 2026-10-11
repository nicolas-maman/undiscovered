"""Check that every relative link in the project's Markdown and HTML points at a file that exists.

    python scripts/check_links.py

Links to other sites are not fetched (CI would then fail when a site is
down); links within the repository are, including #anchors into Markdown
headings, and so are links to this repository's own files on GitHub, which
the site uses. Exit status 1 lists every broken link.
"""

from __future__ import annotations

import pathlib
import re
import sys
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "node_modules", "cache", "data", "data_seed2027", "results", "build"}
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
OWN = re.compile(r"^https://github\.com/nicolas-maman/undiscovered/(?:blob|tree)/main/(.*)$")


def anchors(md: pathlib.Path) -> set[str]:
    """GitHub's anchors for a Markdown file's headings."""
    out = set()
    for line in FENCE.sub("", md.read_text(encoding="utf-8")).splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))     # a link keeps its text
            text = re.sub(r"[`*]", "", text).strip().lower()
            out.add(re.sub(r"[^\w\- ]", "", text).replace(" ", "-"))
    return out


def files() -> list[pathlib.Path]:
    return [p for p in ROOT.rglob("*")
            if p.is_file() and p.suffix in {".md", ".html"} and not SKIP & set(p.relative_to(ROOT).parts)]


def broken() -> list[str]:
    bad = []
    for page in files():
        text = page.read_text(encoding="utf-8")
        pattern = MD_LINK if page.suffix == ".md" else HTML_LINK
        if page.suffix == ".md":
            text = FENCE.sub("", text)
        for target in pattern.findall(text):
            own = OWN.match(target)
            if not own and (re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith(("//", "{", "$"))):
                continue                                   # another site, mailto:, or a template
            path, _, anchor = unquote(own.group(1) if own else target).partition("#")
            base = ROOT if own else page.parent
            dest = page if not path and not own else (base / path).resolve()
            where = f"{page.relative_to(ROOT).as_posix()}: {target}"
            if not dest.exists():
                bad.append(where)
            elif anchor and dest.suffix == ".md" and anchor.lower() not in anchors(dest):
                bad.append(f"{where} (no such heading)")
    return bad


if __name__ == "__main__":
    problems = broken()
    for p in problems:
        print(p)
    print(f"{len(problems)} broken links" if problems else f"ok: links in {len(files())} files")
    sys.exit(1 if problems else 0)
