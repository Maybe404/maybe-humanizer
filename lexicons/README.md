# lexicons/

阶段 1 只有 `zh.yaml` 一份，用途有两个：

- 核验步骤（02-plan.md 4.5）的语义项计数与复核信号：`qualifiers`、`negations`、`causal_markers`、`first_person`。
- 复扫：`patterns` 下每条规则的触发短语，改写前后各数一遍，得出「仍在」和「新引入」。

`patterns` 不是阶段 2 的扫描器。扫描器要先在人工标注的语料上量误报率（02-plan.md 第 7 节）才进改写步骤；这里的短语只用于事后计数，命中不进候选清单。

词条照录自前一版 `references/patterns-zh.md`，顺序不动。ZH-P-024 的「不是／而是」和 ZH-P-003 的序词在正常中文里大量出现，复扫时它们的计数只作信号，不作判断。
