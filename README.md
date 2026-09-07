# maybe-humanizer

把中文或英文的书面文字改得不像 AI 写的，或者只审不改地指出问题。清掉模式的同时保住事实：数字、条件、限定、否定、责任主体、作者声口一律不动。

这是 Max 版：引擎加薄 skill，代码编排全流程，模型只在诊断裁决、改写、语义判定三个位置出场。方案见 [doc/](doc/)。

## 结构

```
doc/            方案文档（先读 doc/README.md）
engine/         Python 包：protect / prepare / patch / verify / judge / report / pipeline / cli
prompts/        三次模型调用的 prompt 和端到端范例
rules/          规则 YAML，唯一真相源（阶段 1 只有代表规则）
lexicons/       中文词表：核验计数与复扫用
skill/          SKILL.md 路由；cards/ 由 rules/ 生成
evals/          结构化用例、留出样本、运行器、基线记录
tests/          引擎单元测试
```

## 用法

```bash
uv sync --all-groups
uv run pytest
uv run humanizer run draft.md --request "帮我去 AI 味"        # 通过本机 claude -p 跑三次调用
uv run humanizer prepare draft.md --request "帮我去 AI 味"    # 分步：见 skill/SKILL.md
uv run python -m evals.runner --out evals/runs/proto-1       # 跑 eval
```

流水线每一步的产物都落在 `.humanizer/` 下：`prepared.json`、`diagnose.out.md`、`rewrite-r{n}.out.md`、`verify-r{n}.yaml`、`judge.out.md`、`output.md`、`report.md`。

## 核验规则

硬失败退回改写，最多三轮：受保护片段还原后与原文不一致；逐字项缺失；台账缺编号；越过授权范围（in-place 句数变化、bounded 合并或未列清单的删除、校对档结构改动）；补丁引用不存在的句号。

复核信号只标黄：命题限定词减少、否定词变化、因果标记新增、第一人称/emoji/破折号/感叹号新增、字数低于 85%、句数变化超过 10%、复扫新引入多于清掉。85% 和 10% 是继承来的经验值，未在本仓库语料上测过。

## 状态

阶段 1 原型代码已写，未跑通对照实验。阶段 0 的两份基线未跑。见 `evals/baselines/README.md`。
