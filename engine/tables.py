"""Parse the Markdown tables and marked sections the model produces.

Sections are delimited as::

    <<<VERDICT>>>
    | ID | 裁决 | 理由 |
    ...
    <<<END>>>

Tables are parsed loosely: header row, separator row, then data rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SECTION_RE = re.compile(r"<<<([A-Z_]+)>>>(.*?)<<<END>>>", re.DOTALL)


def sections(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in _SECTION_RE.finditer(text)}


def parse_table(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []  # drop header


@dataclass
class Verdict:
    id: str
    verdict: str  # 确认 | 排除 | 待确认 | 新增
    reason: str
    sentence: str = ""
    rule: str = ""
    trigger: str = ""
    fix: str = ""


VERDICT_VALUES = ("确认", "排除", "待确认", "新增")


def parse_verdicts(block: str) -> list[Verdict]:
    """Columns: ID | 句 | 规则 | 触发 | 裁决 | 理由 | 修法 (any prefix subset).

    The diagnose prompt asks for exactly this seven-column table; F rows may
    omit trailing cells.
    """
    out: list[Verdict] = []
    for cells in parse_table(block):
        if not cells or not cells[0]:
            continue
        raw_len = len(cells)
        cells = cells + [""] * (7 - len(cells))
        vid = cells[0]
        if raw_len >= 5:
            out.append(
                Verdict(
                    id=vid,
                    sentence=cells[1],
                    rule=cells[2],
                    trigger=cells[3],
                    verdict=cells[4],
                    reason=cells[5],
                    fix=cells[6],
                )
            )
        else:  # short form: ID | 裁决 | 理由
            out.append(Verdict(id=vid, verdict=cells[1], reason=cells[2]))
    return out


@dataclass
class LedgerRow:
    id: str
    action: str  # 已改 | 保留 | 待确认
    note: str


LEDGER_VALUES = ("已改", "保留", "待确认")


def parse_ledger(block: str) -> list[LedgerRow]:
    out: list[LedgerRow] = []
    for cells in parse_table(block):
        if not cells or not cells[0]:
            continue
        cells = cells + [""] * (3 - len(cells))
        out.append(LedgerRow(id=cells[0], action=cells[1], note=cells[2]))
    return out


@dataclass
class PendingDeletion:
    sentence: int
    original: str
    reason: str


def parse_pending(block: str) -> list[PendingDeletion]:
    out: list[PendingDeletion] = []
    for cells in parse_table(block):
        if not cells:
            continue
        cells = cells + [""] * (3 - len(cells))
        m = re.search(r"\d+", cells[0])
        if not m:
            continue
        out.append(PendingDeletion(sentence=int(m.group(0)), original=cells[1], reason=cells[2]))
    return out


@dataclass
class JudgeRow:
    block: str
    result: str  # 通过 | 失真 | 需作者确认
    item: str
    note: str


JUDGE_VALUES = ("通过", "失真", "需作者确认")


def parse_judge(block: str) -> list[JudgeRow]:
    out: list[JudgeRow] = []
    for cells in parse_table(block):
        if not cells:
            continue
        cells = cells + [""] * (4 - len(cells))
        out.append(JudgeRow(block=cells[0], result=cells[1], item=cells[2], note=cells[3]))
    return out
