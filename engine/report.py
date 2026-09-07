"""Step 4.7: delivery text generated from the ledger, diff and verify report."""

from __future__ import annotations

from engine.prepare import Prepared
from engine.tables import JudgeRow, LedgerRow, PendingDeletion, Verdict
from engine.verify import Report

MAX_NOTES = 6


def _rule_of(vid: str, verdicts: list[Verdict]) -> str:
    for v in verdicts:
        if v.id == vid:
            return v.rule or ""
    return ""


def _sentence_of(vid: str, verdicts: list[Verdict]) -> str:
    for v in verdicts:
        if v.id == vid:
            return v.sentence or ""
    return ""


def review_report(prep: Prepared, verdicts: list[Verdict]) -> str:
    confirmed = [v for v in verdicts if v.verdict in ("确认", "新增")]
    pending = [v for v in verdicts if v.verdict == "待确认"]
    lines = [prep.triage_line, ""]
    if prep.axes.short_text:
        lines.append("样本太短（中文不足 80 字或英文不足 40 词），只列具体命中，不给整体判定。")
    else:
        n = len(confirmed)
        lines.append(f"结论：命中模式 {n} 处。" if n else "结论：无需编辑。")
    lines.append("")

    def block(title: str, rows: list[Verdict]) -> None:
        if not rows:
            return
        lines.append(f"## {title}")
        for v in rows[:MAX_NOTES]:
            lines.append(
                f"- {v.rule or '未归规则'}｜第 {v.sentence or '?'} 句｜触发：{v.trigger or v.reason}｜建议：{v.fix or '见理由'}"
            )
        if len(rows) > MAX_NOTES:
            lines.append(f"- 另有 {len(rows) - MAX_NOTES} 条见附录。")
        lines.append("")

    block("确认项", confirmed)
    block("待确认项", pending)
    lines.append("是谁写的由你判断，这里只列模式。要接着改可以说一声。")
    return "\n".join(lines)


def rewrite_report(
    prep: Prepared,
    rep: Report,
    ledger: list[LedgerRow],
    verdicts: list[Verdict],
    pending: list[PendingDeletion],
    judge: list[JudgeRow],
    *,
    rounds: int,
    partial: bool = False,
) -> str:
    changed = [r for r in ledger if r.action == "已改"]
    kept = [r for r in ledger if r.action != "已改"]
    lines: list[str] = []
    if partial:
        lines.append("这是阶段稿，不是终稿：语义判定仍有失真项未解决，见「需作者确认」。")
    lines.append("## 改动说明")
    lines.append(prep.triage_line)
    for r in changed[:MAX_NOTES]:
        rid = _rule_of(r.id, verdicts)
        lines.append(f"- {r.id}{'（' + rid + '）' if rid else ''}：{r.note}")
    if len(changed) > MAX_NOTES:
        lines.append(f"- 另有 {len(changed) - MAX_NOTES} 处改动见附录。")
    lines.append("")
    lines.append("## 残留清单")
    if kept:
        for r in kept[:MAX_NOTES]:
            rid = _rule_of(r.id, verdicts)
            sid = _sentence_of(r.id, verdicts)
            lines.append(
                f"- {r.id}{'（' + rid + '）' if rid else ''}{'，第 ' + sid + ' 句' if sid else ''}：{r.action}，{r.note}"
            )
    else:
        lines.append("- 无")
    if rep.rescan.get("remaining"):
        lines.append(f"- 复扫仍有命中的规则：{', '.join(rep.rescan['remaining'])}")
    if rep.rescan.get("introduced"):
        lines.append(f"- 复扫发现改写新引入的规则命中：{', '.join(rep.rescan['introduced'])}")
    lines.append("")
    if pending:
        lines.append("## 建议删除（待确认）")
        for p in pending:
            lines.append(f"- 第 {p.sentence} 句：{p.original}｜{p.reason}")
        lines.append("")
    distortions = [j for j in judge if j.result != "通过"]
    if distortions:
        lines.append("## 需作者确认")
        for j in distortions:
            lines.append(
                f"- {j.block}：{j.result}{'（' + j.item + '）' if j.item else ''}，{j.note}"
            )
        lines.append("")
    lines.append("## 前提声明")
    lines.append(f"- 体裁自动判定：{prep.axes.genre}，依据：{prep.axes.genre_clue}。")
    lines.append("- 词表：本仓库 lexicons/zh.yaml，未使用用户或项目词表。")
    if rep.signals:
        kinds = ", ".join(s["kind"] for s in rep.signals)
        lines.append(f"- 复核信号（不阻断）：{kinds}。")
    lines.append(f"- 轮数：{rounds}。")
    return "\n".join(lines)
