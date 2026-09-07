# 文档索引

这套文档是 maybe-humanizer 的开工依据。按顺序读：

| 文件 | 内容 | 谁读 |
|---|---|---|
| [01-background.md](01-background.md) | 背景、出发点、前一版 skill 的评估结论、六份外部反馈的汇总 | 想知道"为什么这么做"的人 |
| [02-plan.md](02-plan.md) | 最终方案：仓库结构、流水线、三次模型调用的职责、核验与阻断项、阶段与完成定义、授权边界 | 执行者，每个阶段开工前重读 |
| [03-formats.md](03-formats.md) | 各步骤的输入输出格式：句子编号、占位符、候选清单、台账、补丁、核验报告、eval 用例 schema | 写引擎和写 SKILL.md 的人 |
| [04-phase0-contract-fixes.md](04-phase0-contract-fixes.md) | 阶段 0 要修的四处契约矛盾，逐处写位置、现状、改法 | 阶段 0 执行者 |
| [05-editions.md](05-editions.md) | Max、Plus、Air 三个版本的定义与边界，后两个只记录，现在不做 | 规划时看 |

术语（首次出现时括注）：skill（给模型读的任务说明包）、prompt（发给模型的指令）、eval（验收用例）、ledger（台账，模型对每个编号问题的处理记录）、invariant（不变量，改写前后必须原样存在的内容）。

## 现有成果在哪

本仓库是空的，所有已有内容都在前一个仓库 `github.com/Maybe404/skill`（本机路径 `/Users/maybe/code/github.com/Maybe404/skill`），基线用的版本是 commit `37e96bf`。执行前先把下面这些读一遍：

| 路径 | 内容 | 本仓库怎么用 |
|---|---|---|
| `skills/maybe-humanizer/SKILL.md` | 前一版主文件，140 行，五步流程摘要 | 阶段 0 跑原版基线的对象；阶段 2 生成新 SKILL.md 时参考它的模式划分 |
| `skills/maybe-humanizer/references/protection.md` | 46 条事实保护规则 | 五条保护铁律和逐字项、语义项的定义来源 |
| `skills/maybe-humanizer/references/process.md` | 54 条流程规则，含裁决顺序、四条轴、编辑范围三档、待确认删除清单 | 流水线各步的判据来源；阶段 0 要改的契约矛盾在这里 |
| `skills/maybe-humanizer/references/patterns-zh.md` | 30 条中文模式，词表照录自上游 | 阶段 2 抽词表到 lexicons/ |
| `skills/maybe-humanizer/references/patterns-en.md` | 79 条英文模式，含三档词表 | 阶段 3 |
| `skills/maybe-humanizer/references/patterns-common.md` | 13 条中英通用模式 | 阶段 2 |
| `skills/maybe-humanizer/references/genres.md` | 10 条体裁与语境规则，六档语境、三种触发强度 | 分诊的形式线索和体裁强度表 |
| `skills/maybe-humanizer/references/measurement.md` | 18 条度量规则：什么算证据、阈值、验收 | 核验器的硬失败与复核信号划分 |
| `skills/maybe-humanizer/references/conflicts.md` | 34 条被拒规则和理由 | 只进给人读的文档，不进卡片 |
| `skills/maybe-humanizer/references/optional.md` | 17 条默认不启用的做法 | 声口等可选项 |
| `skills/maybe-humanizer/evals/evals.json` | 26 条 eval，自然语言 expected_output | 阶段 0 的基线样本；阶段 1 按 03-formats.md 结构化 |
| `skills/maybe-humanizer/SOURCES.md` | 10 个已合并来源与 49 个已登记来源、许可证 | 来源与许可文档的依据 |
| `merges/maybe-humanizer/decisions.yaml` | 307 条规则的完整裁决记录、来源、关系 | 规则 YAML 的来源与裁决字段从这里导入 |
| `merges/maybe-humanizer/reports/0001` 到 `0006` | 六次合并报告 | 背景材料 |
| `merges/maybe-humanizer/snapshots/` | 上游快照 | 阶段 2 补词表时查原文 |
| `tools/upstream-monitor/` | 上游监控与同步 CLI | 后续更新用，暂不迁移 |
| `skills/skill-merge/references/criteria.md` | 合并的十条取舍准则 | 新规则进入 rules/ 时沿用 |

前一版的全部规则文本都是中文，规则 id 形如 `ALL-PROC-023`、`ZH-P-001`、`EN-P-026`，本仓库沿用同一套 id。
