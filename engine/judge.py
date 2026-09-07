"""Step 4.6 input: change blocks for the independent semantic judge."""

from __future__ import annotations

from engine.patch import ChangeBlock


def render_blocks(blocks: list[ChangeBlock]) -> str:
    """One group per block: range, original, rewritten, one sentence each side."""
    parts: list[str] = []
    for b in blocks:
        parts.append(
            "\n".join(
                [
                    f"### 块 {b.label}",
                    f"前一句：{b.context_before or '（无）'}",
                    f"原文：{b.before}",
                    f"改文：{b.after or '（整句删除）'}",
                    f"后一句：{b.context_after or '（无）'}",
                ]
            )
        )
    return "\n\n".join(parts) if parts else "（没有字面改动）"
