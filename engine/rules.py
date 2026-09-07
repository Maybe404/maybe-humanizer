"""Load rules/ YAML and render model-facing cards."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "rules"
CARDS_DIR = ROOT / "skill" / "cards"


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(RULES_DIR.rglob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "id" in data:
            out[data["id"]] = data
    return out


def render_card(rule: dict) -> str:
    lines = [f"### {rule['id']} {rule.get('title', '')}".rstrip(), ""]
    lines.append(f"**判据。** {str(rule.get('criterion', '')).strip()}")
    lines.append("")
    lines.append(f"**修法。** {str(rule.get('fix', '')).strip()}")
    lines.append("")
    lines.append(f"**通过条件。** {str(rule.get('pass_when', '')).strip()}")
    lines.append("")
    if rule.get("known_misses"):
        lines.append(f"**已知会漏掉什么。** {str(rule['known_misses']).strip()}")
        lines.append("")
    for ex in rule.get("examples", []) or []:
        if "good" in ex:
            lines.append(f"- 正例：{ex['good']}")
        if "bad" in ex:
            why = f" 违反点：{ex['why']}" if ex.get("why") else ""
            lines.append(f"- 反例：{ex['bad']}{why}")
    return "\n".join(lines).rstrip() + "\n"


def cards_for(lang: str, ids: list[str] | None = None) -> str:
    """Cards for the given ids, or every rule with a detector for the language."""
    rules = load_all()
    if ids:
        chosen = [rules[i] for i in ids if i in rules]
    else:
        chosen = [r for r in rules.values() if r.get("lang") in (lang, "both")]
    return "\n".join(render_card(r) for r in chosen)


def write_cards() -> list[Path]:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for rid, rule in load_all().items():
        p = CARDS_DIR / f"{rid}.md"
        p.write_text(render_card(rule), encoding="utf-8")
        written.append(p)
    return written
