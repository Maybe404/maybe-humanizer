# 文档索引

这套文档是 maybe-humanizer 的开工依据。按顺序读：

| 文件 | 内容 | 谁读 |
|---|---|---|
| [01-background.md](01-background.md) | 背景、出发点、前一版 skill 的评估结论、六份外部反馈的汇总 | 想知道"为什么这么做"的人 |
| [02-plan.md](02-plan.md) | 最终方案：仓库结构、流水线、三次模型调用的职责、核验与阻断项、阶段与完成定义、授权边界 | 执行者，每个阶段开工前重读 |
| [03-formats.md](03-formats.md) | 各步骤的输入输出格式：句子编号、占位符、候选清单、台账、补丁、核验报告、eval 用例 schema | 写引擎和写 SKILL.md 的人 |
| [04-phase0-contract-fixes.md](04-phase0-contract-fixes.md) | 阶段 0 要修的四处契约矛盾，逐处写位置、现状、改法 | 阶段 0 执行者 |

术语（首次出现时括注）：skill（给模型读的任务说明包）、prompt（发给模型的指令）、eval（验收用例）、ledger（台账，模型对每个编号问题的处理记录）、invariant（不变量，改写前后必须原样存在的内容）。

前一版 skill 在 `github.com/Maybe404/skill` 仓库的 `skills/maybe-humanizer/`，它的合并工作台在同仓库 `merges/maybe-humanizer/`。本仓库不复制那些内容，阶段 1 之后用脚本导入需要的部分。
