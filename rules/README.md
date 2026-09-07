# rules/

规则 YAML 是唯一真相源。`skill/cards/` 和 `docs-generated/` 由 `humanizer gen-cards` 从这里生成，不手工编辑。

阶段 1 只放少量代表规则，用来跑通原型；schema 在阶段 1 原型对照结果出来之后再定稿（02-plan.md 第 5 节）。下面是暂定字段，`severity` 和 `frequency` 是 05-editions.md 要求预留的两个排序字段，现在可以为空。

```yaml
id: ZH-P-001                # 沿用前一版 id
lang: zh                    # zh | en | both
category: pattern           # protection | process | pattern | genre | measurement | optional
title: 中文高频词与元叙述
criterion: |                # 判据
fix: |                      # 修法
pass_when: |                # 通过条件（什么时候不算命中）
known_misses: |             # 已知会漏掉什么
examples:
  - good: ...
  - bad: ...
    why: ...                # 违反点
detector:                   # 可空。有检测器的规则才卡片化
  kind: lexicon             # lexicon | regex | count
  lexicon: ZH-P-001         # 指向 lexicons/zh.yaml 的 patterns 键
severity: null              # 1 生成残留与无源断言 | 2 一眼能认出的模式 | 3 风格打磨（ALL-M-022 三档）
frequency: null             # 语料命中频率，阶段 2 之后填
genre_strength:             # 标准 | 放宽 | 加严；没写的档位按标准
  短社交帖: 放宽
source:                     # 来源与裁决记录，只进给人读的文档
  decision: adopted         # adopted | adapted | rejected | reference | deferred
  from: [...]
```

给模型的卡片只含 title、criterion、fix、pass_when、known_misses 和 examples。
