"""The volunteer's settings, kept on their own machine and nowhere else."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "undiscovered" / "config.json"


def load() -> dict:
    p = path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(cfg: dict) -> Path:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    try:
        p.chmod(0o600)      # only the volunteer can read their keys (where the system allows it)
    except OSError:
        pass
    return p


def openalex_key(cfg: dict) -> str:
    return os.environ.get("OPENALEX_API_KEY") or cfg.get("openalex_key", "")
