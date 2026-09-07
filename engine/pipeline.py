"""Code-driven orchestration. The model appears at three points only.

Every step reads and writes files under a work directory so that a host model
(Claude Code and the like) can drive the same steps by hand:

    prepared.json            step 1 output
    diagnose.prompt.md       step 3 input     diagnose.out.md      model output
    rewrite-r{n}.prompt.md   step 4 input     rewrite-r{n}.out.md  model output
    verify-r{n}.yaml         step 5 output
    judge.prompt.md          step 6 input     judge.out.md         model output
    output.md                restored text of the accepted round
    report.md                delivery text
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

from engine import patch as P
from engine import report as R
from engine import rules, tables
from engine.judge import render_blocks
from engine.prepare import Prepared, prepare
from engine.verify import Report, verify

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
MAX_VERIFY_ROUNDS = 3
MAX_JUDGE_ROUNDS = 1


class Backend(Protocol):
    def complete(self, prompt: str) -> str: ...


@dataclass
class ClaudeCli:
    """Call the local ``claude -p`` binary. Temperature is not controllable here."""

    model: str | None = None
    binary: str = "claude"

    def complete(self, prompt: str) -> str:
        if shutil.which(self.binary) is None:
            msg = f"{self.binary} not found on PATH"
            raise RuntimeError(msg)
        cmd = [self.binary, "-p", "--output-format", "text"]
        if self.model:
            cmd += ["--model", self.model]
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            msg = f"{self.binary} exited {proc.returncode}: {proc.stderr[-2000:]}"
            raise RuntimeError(msg)
        return proc.stdout


@dataclass
class Replay:
    """Serve pre-recorded outputs in order; for tests and evals without a model."""

    outputs: list[str]
    calls: int = 0

    def complete(self, prompt: str) -> str:  # noqa: ARG002
        if self.calls >= len(self.outputs):
            msg = "Replay backend exhausted"
            raise RuntimeError(msg)
        out = self.outputs[self.calls]
        self.calls += 1
        return out


# ---------------------------------------------------------------- prompts


def _template(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _example_for(prep: Prepared) -> str:
    name = {
        "structural": "rewrite-structural",
        "bounded": "rewrite-bounded",
        "in-place": "rewrite-inplace",
    }[prep.axes.scope]
    p = PROMPTS / "examples" / f"{name}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _literal_table(prep: Prepared) -> str:
    if not prep.literal:
        return "（无）"
    return "\n".join(f"- 第 {i.sentence} 句：{i.text}（{i.kind}）" for i in prep.literal)


def build_diagnose_prompt(prep: Prepared, candidates: str = "") -> str:
    cards = rules.cards_for(prep.lang)
    return "\n\n".join(
        [
            _template("diagnose"),
            "## 分诊声明\n\n" + prep.triage_line,
            "## 候选清单（扫描输出）\n\n"
            + (
                candidates.strip()
                or "（本轮没有接扫描器，候选清单为空，全部问题由你按 S 编号新增）"
            ),
            "## 规则卡片\n\n" + cards,
            "## 编号正文\n\n" + prep.numbered(),
        ]
    )


def verdict_table(verdicts: list[tables.Verdict]) -> str:
    rows = ["| ID | 句 | 规则 | 触发 | 裁决 | 理由 | 修法 |", "|---|---|---|---|---|---|---|"]
    for v in verdicts:
        if v.verdict in ("确认", "待确认", "新增"):
            rows.append(
                f"| {v.id} | {v.sentence} | {v.rule} | {v.trigger} | {v.verdict} | {v.reason} | {v.fix} |"
            )
    return "\n".join(rows)


def build_rewrite_prompt(
    prep: Prepared,
    verdicts: list[tables.Verdict],
    *,
    failures: list[dict] | None = None,
    judge_rows: list[tables.JudgeRow] | None = None,
    previous_output: str | None = None,
) -> str:
    ax = prep.axes
    parts = [
        _template("rewrite"),
        "## 本次四条轴\n\n" + prep.triage_line,
        "## 逐字项（改写后必须原样存在）\n\n" + _literal_table(prep),
        "## 裁决后的问题清单\n\n" + verdict_table(verdicts),
        "## 范例\n\n" + _example_for(prep),
        "## 编号正文\n\n" + prep.numbered(),
    ]
    if failures:
        fl = "\n".join(f"- {json.dumps(f, ensure_ascii=False)}" for f in failures)
        parts.append("## 上一轮核验失败项（只需修这些，其余沿用上一轮）\n\n" + fl)
    if judge_rows:
        jl = "\n".join(
            f"- {j.block}：{j.result}（{j.item}）{j.note}" for j in judge_rows if j.result == "失真"
        )
        parts.append("## 语义判定认定的失真项（改回原意，其余沿用上一轮）\n\n" + jl)
    if previous_output:
        parts.append("## 上一轮输出\n\n" + previous_output)
    _ = ax
    return "\n\n".join(parts)


def build_judge_prompt(blocks: list[P.ChangeBlock]) -> str:
    return "\n\n".join([_template("judge"), "## 变更块\n\n" + render_blocks(blocks)])


# ---------------------------------------------------------------- steps


@dataclass
class RoundResult:
    applied: P.ApplyResult
    patches: list[P.Patch]
    ledger: list[tables.LedgerRow]
    pending: list[tables.PendingDeletion]
    report: Report
    raw: str


def parse_rewrite_output(
    prep: Prepared, raw: str, verdicts: list[tables.Verdict], round_no: int
) -> RoundResult:
    secs = tables.sections(raw)
    patches, parse_fail = P.parse_patches(secs.get("PATCH", ""))
    ledger = tables.parse_ledger(secs.get("LEDGER", ""))
    pending = tables.parse_pending(secs.get("PENDING", ""))
    applied = P.apply(prep.sentences, patches)
    applied.failures = parse_fail + applied.failures
    if "PATCH" not in secs:
        applied.failures.append(
            {"kind": "patch_invalid", "item": "PATCH", "reason": "缺少 <<<PATCH>>> 区块"}
        )
    if "LEDGER" not in secs:
        applied.failures.append(
            {"kind": "ledger_missing", "id": "*", "reason": "缺少 <<<LEDGER>>> 区块"}
        )
    rep = verify(prep, applied, patches, ledger, verdicts, pending, round_no=round_no)
    return RoundResult(
        applied=applied, patches=patches, ledger=ledger, pending=pending, report=rep, raw=raw
    )


def _dump_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


@dataclass
class RunResult:
    mode: str
    output_text: str
    report_text: str
    rounds: int
    verify: Report | None
    judge: list[tables.JudgeRow]
    partial: bool
    stop_reason: str | None = None


def run(
    body: str,
    request: str,
    backend: Backend,
    workdir: Path,
    *,
    file_path: str | None = None,
) -> RunResult:
    workdir.mkdir(parents=True, exist_ok=True)
    prep = prepare(body, request, file_path=file_path)
    (workdir / "prepared.json").write_text(
        json.dumps(prep.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if prep.stop_reason:
        (workdir / "report.md").write_text(prep.stop_reason, encoding="utf-8")
        return RunResult(prep.axes.mode, "", prep.stop_reason, 0, None, [], False, prep.stop_reason)

    # step 3: diagnose
    dprompt = build_diagnose_prompt(prep)
    (workdir / "diagnose.prompt.md").write_text(dprompt, encoding="utf-8")
    dout = backend.complete(dprompt)
    (workdir / "diagnose.out.md").write_text(dout, encoding="utf-8")
    verdicts = tables.parse_verdicts(tables.sections(dout).get("VERDICT", ""))

    if prep.axes.mode == "review":
        text = R.review_report(prep, verdicts)
        (workdir / "report.md").write_text(text, encoding="utf-8")
        return RunResult("review", "", text, 1, None, [], False)

    # step 4/5: rewrite + verify, up to MAX_VERIFY_ROUNDS
    rr: RoundResult | None = None
    failures: list[dict] | None = None
    prev: str | None = None
    rounds = 0
    for n in range(1, MAX_VERIFY_ROUNDS + 1):
        rounds = n
        rprompt = build_rewrite_prompt(prep, verdicts, failures=failures, previous_output=prev)
        (workdir / f"rewrite-r{n}.prompt.md").write_text(rprompt, encoding="utf-8")
        rout = backend.complete(rprompt)
        (workdir / f"rewrite-r{n}.out.md").write_text(rout, encoding="utf-8")
        rr = parse_rewrite_output(prep, rout, verdicts, n)
        _dump_yaml(workdir / f"verify-r{n}.yaml", rr.report.to_dict())
        if rr.report.status != "fail":
            break
        failures, prev = rr.report.hard_failures, rout
    assert rr is not None
    if rr.report.status == "fail":
        text = "核验三轮仍有硬失败，未交付。失败项见 verify-r*.yaml。"
        (workdir / "report.md").write_text(text, encoding="utf-8")
        return RunResult(prep.axes.mode, "", text, rounds, rr.report, [], True)

    # step 6: semantic judge
    judge_rows: list[tables.JudgeRow] = []
    if rr.applied.blocks:
        jprompt = build_judge_prompt(rr.applied.blocks)
        (workdir / "judge.prompt.md").write_text(jprompt, encoding="utf-8")
        jout = backend.complete(jprompt)
        (workdir / "judge.out.md").write_text(jout, encoding="utf-8")
        judge_rows = tables.parse_judge(tables.sections(jout).get("JUDGE", ""))
        distorted = [j for j in judge_rows if j.result == "失真"]
        if distorted and MAX_JUDGE_ROUNDS:
            rounds += 1
            n = rounds
            rprompt = build_rewrite_prompt(
                prep, verdicts, judge_rows=judge_rows, previous_output=rr.raw
            )
            (workdir / f"rewrite-r{n}.prompt.md").write_text(rprompt, encoding="utf-8")
            rout = backend.complete(rprompt)
            (workdir / f"rewrite-r{n}.out.md").write_text(rout, encoding="utf-8")
            rr2 = parse_rewrite_output(prep, rout, verdicts, n)
            _dump_yaml(workdir / f"verify-r{n}.yaml", rr2.report.to_dict())
            if rr2.report.status != "fail":
                rr = rr2
                jprompt = build_judge_prompt(rr.applied.blocks)
                (workdir / "judge-r2.prompt.md").write_text(jprompt, encoding="utf-8")
                jout = backend.complete(jprompt)
                (workdir / "judge-r2.out.md").write_text(jout, encoding="utf-8")
                judge_rows = tables.parse_judge(tables.sections(jout).get("JUDGE", ""))
    partial = any(j.result == "失真" for j in judge_rows)

    output = rr.report.output_text
    (workdir / "output.md").write_text(output, encoding="utf-8")
    text = R.rewrite_report(
        prep, rr.report, rr.ledger, verdicts, rr.pending, judge_rows, rounds=rounds, partial=partial
    )
    (workdir / "report.md").write_text(text, encoding="utf-8")
    return RunResult(prep.axes.mode, output, text, rounds, rr.report, judge_rows, partial)
