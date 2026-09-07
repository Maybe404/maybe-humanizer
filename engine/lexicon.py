"""Load lexicons/*.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LEXICON_DIR = ROOT / "lexicons"


@lru_cache(maxsize=4)
def load(lang: str = "zh") -> dict:
    path = LEXICON_DIR / f"{lang}.yaml"
    if not path.exists():
        return {
            "qualifiers": [],
            "negations": [],
            "causal_markers": [],
            "first_person": [],
            "patterns": {},
        }
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("qualifiers", [])
    data.setdefault("negations", [])
    data.setdefault("causal_markers", [])
    data.setdefault("first_person", [])
    data.setdefault("patterns", {})
    return data


def count_phrases(text: str, phrases: list[str]) -> int:
    return sum(text.count(p) for p in phrases if p)


def phrase_hits(text: str, patterns: dict[str, list[str]]) -> dict[str, int]:
    """Per-rule hit counts, used only for the rescan signal."""
    return {rule: count_phrases(text, words) for rule, words in patterns.items()}
