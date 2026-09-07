# 基线记录

阶段 0 要入库两份：

| 文件 | 对象 | 状态 |
|---|---|---|
| `baseline-original.yaml` | 前一版 skill，commit `37e96bf`，未修契约 | 已入库（2026-09-07，claude-sonnet-5，17 条） |
| `baseline-fixed.yaml` | 前一版 skill，commit `991c382`（修完 04-phase0-contract-fixes.md 四处矛盾） | 未跑 |

运行条件要固定并记录：模型 id、温度（`claude -p` 不能设温度，记为不可控）、prompt 版本（skill 的 commit）。每条用例按四类记：`missed_detection`（漏检）、`missed_handling`（漏处理）、`wrong_edit`（误改）、`out_of_scope`（越界）。

跑法：把前一版 `skills/maybe-humanizer/` 装成 skill，对 `evals/cases/` 的每条用例把 `request` 加空行加 `body` 作为用户消息发给模型，保存原始输出到 `evals/runs/baseline-original/case-<id>.md`，人工对照 `judge_rubric` 和机械断言填四类字段。修正版同法，只应在第 6、9、11、20、26 条和分诊提问行为上出现差异。
