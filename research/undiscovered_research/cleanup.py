"""Remove what the research code leaves on disk, and say how much it freed.

    python -m undiscovered_research.cleanup            # caches only
    python -m undiscovered_research.cleanup --models   # and downloaded embedding models
    python -m undiscovered_research.cleanup --data     # and the collected data and results

By default only things that can be rebuilt are removed: the OpenAlex response
cache, cached embeddings and Python's own caches. Collected data and results
go only with ``--data``, and downloaded models only with ``--models``. Only
the paths listed here are touched. Do not run it during a collection: the
run would have to fetch again what it had cached.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent.parent
MODELS = ("BAAI/bge-small-en-v1.5", "BAAI/bge-base-en-v1.5")   # the robustness checks' models


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _remove(path: Path) -> int:
    if not path.exists():
        return 0
    size = _size(path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return size


def cache_paths() -> list[Path]:
    paths = [RESEARCH / "cache", RESEARCH / ".pytest_cache"]       # the first: older runs' cache
    paths += [d / sub for d in (RESEARCH / "data", RESEARCH / "data_seed2027") for sub in ("cache", "emb")]
    paths += sorted(RESEARCH.rglob("__pycache__"))
    return paths


def data_paths() -> list[Path]:
    return [RESEARCH / "data", RESEARCH / "data_seed2027", RESEARCH / "results"]


def model_paths() -> list[Path]:
    hub = Path(os.environ.get("HF_HUB_CACHE") or
               Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub")
    return [hub / ("models--" + m.replace("/", "--")) for m in MODELS]


def clean_response_cache(path: Path) -> int:
    """Called by the collector once a sample is complete, for that sample's cache only."""
    return _remove(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--models", action="store_true", help="also remove the downloaded embedding models")
    ap.add_argument("--data", action="store_true", help="also remove collected data and results")
    args = ap.parse_args()
    paths = cache_paths() + (model_paths() if args.models else []) + (data_paths() if args.data else [])
    freed = 0
    for p in paths:
        n = _remove(p)
        if n:
            print(f"removed {p} ({n / 1e6:.1f} MB)")
        freed += n
    print(f"freed {freed / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
