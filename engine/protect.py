"""Step 4.1 gates and placeholders: file type, credentials, protected blocks.

Placeholders look like ``⟦CODE-1⟧``. Only whole pieces of content are replaced:
frontmatter, fenced code blocks, tables, inline code, URLs. Numbers, dates,
versions, quotes and qualifiers stay in the prose so the model can see them;
they are checked afterwards through the literal/semantic tables.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

NON_PROSE_SUFFIXES = {
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".env",
    ".csv",
    ".tsv",
    ".lock",
    ".ini",
    ".xml",
    ".sql",
    ".sh",
    ".rb",
    ".php",
    ".swift",
    ".kt",
}

PLACEHOLDER_RE = re.compile(r"⟦([A-Z]+)-(\d+)⟧")

_CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    (
        "password_assignment",
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|api[_\- ]?key|access[_\- ]?token)\s*[:=]\s*\S{6,}"
        ),
    ),
    ("session_cookie", re.compile(r"(?i)\b(sessionid|session_id|PHPSESSID|JSESSIONID)=\S{8,}")),
]
_PLACEHOLDER_VALUES = re.compile(
    r"(?i)(YOUR_|xxxx|<[^>]+>|\*{4,}|\.{3,}|example|placeholder|redacted)"
)


@dataclass
class Placeholder:
    id: str
    kind: str
    text: str
    sentence: int | None = None


@dataclass
class Protected:
    text: str
    placeholders: list[Placeholder] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"text": self.text, "placeholders": [asdict(p) for p in self.placeholders]}


def is_prose_path(path: str) -> bool:
    """ALL-PROC-017: source code, config and structured data are not prose."""
    lower = path.lower()
    return not any(lower.endswith(s) for s in NON_PROSE_SUFFIXES)


def find_credentials(text: str) -> list[str]:
    """ALL-PROT-011: return the kinds of credential-shaped strings found.

    Obvious placeholders (YOUR_API_KEY, xxxx, <token>) do not trigger.
    """
    kinds: list[str] = []
    for kind, pat in _CREDENTIAL_PATTERNS:
        for m in pat.finditer(text):
            if _PLACEHOLDER_VALUES.search(m.group(0)):
                continue
            kinds.append(kind)
            break
    return kinds


class _Allocator:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.items: list[Placeholder] = []

    def add(self, kind: str, text: str) -> str:
        self.counters[kind] = self.counters.get(kind, 0) + 1
        pid = f"{kind}-{self.counters[kind]}"
        self.items.append(Placeholder(id=pid, kind=kind, text=text))
        return f"⟦{pid}⟧"


_FENCE_RE = re.compile(r"^([ \t]*)(```|~~~)")
_TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
_URL_RE = re.compile(r"(?<![\w⟦])(?:https?://|www\.)[^\s<>()\"'）」』】,，。;；]+")
_INLINE_CODE_RE = re.compile(r"`+[^`\n]+?`+")


def protect(text: str) -> Protected:
    """Replace protected blocks with placeholders, keeping a mapping."""
    alloc = _Allocator()
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    # frontmatter: only at the very top
    if n and lines[0].strip() == "---":
        for j in range(1, n):
            if lines[j].strip() in ("---", "..."):
                block = "\n".join(lines[: j + 1])
                out.append(alloc.add("FM", block))
                i = j + 1
                break

    while i < n:
        line = lines[i]
        m = _FENCE_RE.match(line)
        if m:
            fence = m.group(2)
            j = i + 1
            while j < n and not (lines[j].strip().startswith(fence) and lines[j].strip() == fence):
                j += 1
            end = min(j, n - 1)
            block = "\n".join(lines[i : end + 1])
            out.append(alloc.add("BLOCK", block))
            i = end + 1
            continue
        if _TABLE_LINE_RE.match(line):
            j = i
            while j < n and _TABLE_LINE_RE.match(lines[j]):
                j += 1
            block = "\n".join(lines[i:j])
            out.append(alloc.add("TABLE", block))
            i = j
            continue
        out.append(line)
        i += 1

    joined = "\n".join(out)
    joined = _INLINE_CODE_RE.sub(lambda mm: alloc.add("CODE", mm.group(0)), joined)
    joined = _URL_RE.sub(lambda mm: alloc.add("URL", mm.group(0)), joined)
    return Protected(text=joined, placeholders=alloc.items)


def restore(text: str, placeholders: list[Placeholder]) -> tuple[str, list[dict]]:
    """Put protected content back. Returns (text, failures).

    A failure is recorded when a placeholder is missing, duplicated, or unknown.
    The engine treats any failure as a hard failure (protected_mismatch).
    """
    failures: list[dict] = []
    by_id = {p.id: p for p in placeholders}
    seen: dict[str, int] = {}
    for m in PLACEHOLDER_RE.finditer(text):
        pid = f"{m.group(1)}-{m.group(2)}"
        seen[pid] = seen.get(pid, 0) + 1
        if pid not in by_id:
            failures.append(
                {"kind": "protected_mismatch", "item": pid, "reason": "unknown placeholder"}
            )
    for pid in by_id:
        c = seen.get(pid, 0)
        if c == 0:
            failures.append(
                {"kind": "protected_mismatch", "item": pid, "reason": "placeholder missing"}
            )
        elif c > 1:
            failures.append(
                {
                    "kind": "protected_mismatch",
                    "item": pid,
                    "reason": f"placeholder appears {c} times",
                }
            )

    def _sub(mm: re.Match[str]) -> str:
        pid = f"{mm.group(1)}-{mm.group(2)}"
        return by_id[pid].text if pid in by_id else mm.group(0)

    return PLACEHOLDER_RE.sub(_sub, text), failures


def attach_sentences(placeholders: list[Placeholder], sentences: list) -> None:
    """Fill ``Placeholder.sentence`` from the numbered sentences."""
    for p in placeholders:
        token = f"⟦{p.id}⟧"
        for s in sentences:
            if token in s.text:
                p.sentence = s.id
                break
