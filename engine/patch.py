"""Sentence-level patches (03-formats.md).

Format, one per line::

    [1] -> 新句子。
    [3] -> (删除)
    [5-6] -> 合并后的一句。
    [8] -> 拆出的第一句。 || 拆出的第二句。

Sentences not mentioned are kept verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from engine import text as T

_LINE_RE = re.compile(r"^\s*\[(\d+)(?:\s*-\s*(\d+))?\]\s*->\s*(.*?)\s*$")
DELETE_MARK = "(删除)"
SPLIT_MARK = "||"


@dataclass
class Patch:
    start: int
    end: int
    replacement: list[str]  # [] means delete
    raw: str

    @property
    def is_delete(self) -> bool:
        return not self.replacement

    @property
    def is_merge(self) -> bool:
        return self.end > self.start

    @property
    def is_split(self) -> bool:
        return len(self.replacement) > 1

    @property
    def label(self) -> str:
        return f"[{self.start}]" if self.start == self.end else f"[{self.start}-{self.end}]"


@dataclass
class ChangeBlock:
    """One literally changed region, for the semantic judge (4.6)."""

    label: str
    start: int
    end: int
    before: str
    after: str
    context_before: str
    context_after: str


@dataclass
class ApplyResult:
    sentences: list[T.Sentence]  # new numbering
    blocks: list[ChangeBlock]
    failures: list[dict] = field(default_factory=list)
    scope_violations: list[dict] = field(default_factory=list)


def parse_patches(block: str) -> tuple[list[Patch], list[dict]]:
    patches: list[Patch] = []
    failures: list[dict] = []
    for raw in block.splitlines():
        if not raw.strip():
            continue
        m = _LINE_RE.match(raw)
        if not m:
            failures.append(
                {"kind": "patch_invalid", "item": raw.strip(), "reason": "unparseable line"}
            )
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        body = m.group(3)
        if end < start:
            failures.append(
                {"kind": "patch_invalid", "item": raw.strip(), "reason": "range end before start"}
            )
            continue
        if body.strip() in (DELETE_MARK, "(delete)", "（删除）"):
            repl: list[str] = []
        else:
            repl = [p.strip() for p in body.split(SPLIT_MARK)]
            repl = [p for p in repl if p]
            if not repl:
                failures.append(
                    {"kind": "patch_invalid", "item": raw.strip(), "reason": "empty replacement"}
                )
                continue
        patches.append(Patch(start=start, end=end, replacement=repl, raw=raw.strip()))
    return patches, failures


def check_scope(
    patches: list[Patch], scope: str, strength: str, pending_deletions: set[int]
) -> list[dict]:
    """Authorization checks that can be read off the patch list itself."""
    out: list[dict] = []
    for p in patches:
        if scope == "in-place":
            if p.is_delete:
                out.append(
                    {
                        "kind": "scope_violation",
                        "item": p.label,
                        "reason": "in-place 不允许删除整句",
                    }
                )
            if p.is_merge:
                out.append(
                    {"kind": "scope_violation", "item": p.label, "reason": "in-place 不允许合并"}
                )
            if p.is_split:
                out.append(
                    {"kind": "scope_violation", "item": p.label, "reason": "in-place 不允许拆分"}
                )
        elif scope == "bounded":
            if p.is_merge:
                out.append(
                    {
                        "kind": "scope_violation",
                        "item": p.label,
                        "reason": "bounded 不允许合并相邻句",
                    }
                )
            if p.is_delete and p.start not in pending_deletions:
                out.append(
                    {
                        "kind": "scope_violation",
                        "item": p.label,
                        "reason": "bounded 下整句删除只能进待确认清单，不直接执行",
                    }
                )
        if strength == "proofread" and (p.is_delete or p.is_merge or p.is_split):
            out.append(
                {"kind": "scope_violation", "item": p.label, "reason": "校对档不允许结构改动"}
            )
    return out


def apply(sentences: list[T.Sentence], patches: list[Patch]) -> ApplyResult:
    """Apply patches, renumber, and collect change blocks.

    Hard failures: unknown sentence ids, overlapping ranges, merges across a
    paragraph boundary, patches on protected (placeholder-only) sentences.
    """
    failures: list[dict] = []
    by_id = {s.id: s for s in sentences}
    covered: dict[int, Patch] = {}
    valid: list[Patch] = []
    for p in patches:
        ids = list(range(p.start, p.end + 1))
        bad = [i for i in ids if i not in by_id]
        if bad:
            failures.append(
                {"kind": "patch_invalid", "item": p.label, "reason": f"句号不存在: {bad}"}
            )
            continue
        if any(i in covered for i in ids):
            failures.append(
                {"kind": "patch_invalid", "item": p.label, "reason": "句号区间与另一条补丁重叠"}
            )
            continue
        if any(by_id[i].protected for i in ids) and not (
            len(ids) == 1 and p.replacement == [by_id[ids[0]].text]
        ):
            failures.append(
                {
                    "kind": "protected_mismatch",
                    "item": p.label,
                    "reason": "补丁改动了受保护片段所在句",
                }
            )
            continue
        if p.is_merge and len({by_id[i].paragraph for i in ids}) > 1:
            failures.append(
                {"kind": "patch_invalid", "item": p.label, "reason": "合并跨越了段落边界"}
            )
            continue
        for i in ids:
            covered[i] = p
        valid.append(p)

    new: list[T.Sentence] = []
    blocks: list[ChangeBlock] = []
    i = 0
    n = len(sentences)
    order = sorted(valid, key=lambda p: p.start)
    starts = {p.start: p for p in order}
    while i < n:
        s = sentences[i]
        p = starts.get(s.id)
        if p is None:
            new.append(
                T.Sentence(
                    id=0, text=s.text, sep=s.sep, paragraph=s.paragraph, protected=s.protected
                )
            )
            i += 1
            continue
        span = sentences[i : i + (p.end - p.start + 1)]
        before = "".join(x.text + x.sep for x in span).rstrip()
        last_sep = span[-1].sep
        if p.replacement != [x.text for x in span]:
            ctx_b = sentences[i - 1].text if i > 0 else ""
            ctx_a = sentences[i + len(span)].text if i + len(span) < n else ""
            glue = "" if T.is_chinese(before) else " "
            blocks.append(
                ChangeBlock(
                    label=p.label,
                    start=p.start,
                    end=p.end,
                    before=before,
                    after=glue.join(p.replacement),
                    context_before=ctx_b,
                    context_after=ctx_a,
                )
            )
        if p.is_delete:
            # a deleted paragraph-final sentence hands its paragraph break to the
            # previous sentence; a mid-paragraph deletion drops its separator
            if new and last_sep.count("\n") >= 2:
                new[-1].sep = last_sep
            i += len(span)
            continue
        for k, r in enumerate(p.replacement):
            is_last = k == len(p.replacement) - 1
            sep = last_sep if is_last else ("" if r and r[-1] in "。！？" else " ")
            new.append(
                T.Sentence(id=0, text=r, sep=sep, paragraph=span[0].paragraph, protected=False)
            )
        i += len(span)

    for k, s in enumerate(new, start=1):
        s.id = k
    return ApplyResult(sentences=new, blocks=blocks, failures=failures)
