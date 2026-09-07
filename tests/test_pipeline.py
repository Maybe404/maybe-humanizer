from pathlib import Path

from engine import pipeline, tables
from engine.prepare import prepare

SRC = (
    "值得注意的是，在当前的架构背景下，基于对性能的综合考量，通过一系列的优化措施，"
    "我们将 p99 延迟从 900 毫秒降低到了 40 毫秒。"
    "需要指出的是，该优化仅在开启了 `--enable-cache` 参数时生效，且不适用于 v2.3 之前的版本。"
    "这一成果充分彰显了团队精益求精的工匠精神。"
)

VERDICT = """<<<VERDICT>>>
| ID | 句 | 规则 | 触发 | 裁决 | 理由 | 修法 |
|---|---|---|---|---|---|---|
| S1 | 1 | ZH-P-001/ZH-P-008 | 值得注意的是；三层前置状语 | 新增 | | 主干提前 |
| S2 | 2 | ZH-P-001 | 需要指出的是 | 新增 | | 删掉 |
| S3 | 3 | ZH-P-015 | 充分彰显 | 新增 | 删后第 1 句事实完整 | 整句删除 |
<<<END>>>"""

GOOD_REWRITE = """<<<PATCH>>>
[1] -> 我们把 p99 延迟从 900 毫秒压到了 40 毫秒。
[2] -> 这只在开启 ⟦CODE-1⟧ 参数时生效，v2.3 之前的版本不适用。
[3] -> (删除)
<<<END>>>

<<<LEDGER>>>
| ID | 动作 | 说明 |
|---|---|---|
| S1 | 已改 | 主干提前 |
| S2 | 已改 | 删掉 |
| S3 | 已改 | 整句删除 |
<<<END>>>"""

BAD_REWRITE = """<<<PATCH>>>
[1] -> 我们把 p99 延迟大幅降低了。
[2] -> 这在开启缓存参数时生效。
<<<END>>>

<<<LEDGER>>>
| ID | 动作 | 说明 |
|---|---|---|
| S1 | 已改 | 主干提前 |
<<<END>>>"""

JUDGE_OK = """<<<JUDGE>>>
| 块 | 结论 | 项 | 说明 |
|---|---|---|---|
| [1] | 通过 | | |
| [2] | 通过 | | |
| [3] | 通过 | | 空话整句删除 |
<<<END>>>"""


def test_prepare_tables_and_triage():
    prep = prepare(SRC, "这段技术说明太啰嗦了，帮我改写一下")
    assert prep.lang == "zh"
    assert (
        prep.axes.mode == "rewrite"
        and prep.axes.strength == "rewrite"
        and prep.axes.scope == "structural"
    )
    assert prep.axes.genre == "技术长文"
    lit = {i.text for i in prep.literal}
    assert {"900 毫秒", "40 毫秒", "v2.3"} <= lit
    sem = {(i.text, i.sentence) for i in prep.semantic}
    assert ("仅", 2) in sem
    assert len(prep.sentences) == 3
    assert "⟦CODE-1⟧" in prep.sentences[1].text


def test_bad_rewrite_is_hard_failure_then_good_rewrite_passes(tmp_path: Path):
    backend = pipeline.Replay([VERDICT, BAD_REWRITE, GOOD_REWRITE, JUDGE_OK])
    res = pipeline.run(SRC, "这段技术说明太啰嗦了，帮我改写一下", backend, tmp_path)
    assert backend.calls == 4
    assert res.rounds == 2
    v1 = (tmp_path / "verify-r1.yaml").read_text(encoding="utf-8")
    assert "literal_missing" in v1
    assert "ledger_missing" in v1
    assert "protected_mismatch" in v1
    assert res.verify is not None and res.verify.status in ("pass", "pass_with_signals")
    assert "--enable-cache" in res.output_text
    assert "充分彰显" not in res.output_text
    assert "900 毫秒" in res.output_text
    assert not res.partial
    assert "改动说明" in res.report_text
    assert "轮数：2" in res.report_text


def test_review_mode_stops_after_diagnosis(tmp_path: Path):
    backend = pipeline.Replay([VERDICT])
    res = pipeline.run(SRC, "看看这篇是不是 AI 写的", backend, tmp_path)
    assert res.mode == "review"
    assert backend.calls == 1
    assert "命中模式 3 处" in res.report_text
    assert res.output_text == ""


def test_inplace_scope_blocks_delete():
    prep = prepare(SRC, "帮我去去 AI 味，但一句都别删，句子数量要和原文一样")
    assert prep.axes.scope == "in-place"
    verdicts = tables.parse_verdicts(tables.sections(VERDICT)["VERDICT"])
    rr = pipeline.parse_rewrite_output(prep, GOOD_REWRITE, verdicts, 1)
    kinds = [f["kind"] for f in rr.report.hard_failures]
    assert "scope_violation" in kinds


def test_credential_stop(tmp_path: Path):
    res = pipeline.run(
        "密码是 password=hunter2hunter2 别改", "改一下", pipeline.Replay([]), tmp_path
    )
    assert res.stop_reason
    assert "凭证" in res.report_text
