# 格式约定

所有格式以能被代码解析和能被模型稳定产出为标准。模型输出的部分用 Markdown 表格或带标记的纯文本，不用嵌套 JSON。

## 句子编号

代码给全文编号后交给模型，形如：

```
[1] 值得注意的是，在当前的架构背景下，我们将 p99 延迟从 900 毫秒降低到了 40 毫秒。
[2] 该优化仅在开启了 ⟦CODE-1⟧ 参数时生效，且不适用于 v2.3 之前的版本。
[3] 这一成果充分彰显了团队精益求精的工匠精神。
```

段落之间保留空行，编号跨段连续。

## 占位符

形如 `⟦CODE-1⟧`、`⟦URL-2⟧`、`⟦BLOCK-3⟧`。映射表：

```yaml
- id: CODE-1
  kind: inline_code
  text: "--enable-cache"
  sentence: 2
```

还原时逐字比对，任何差异记硬失败。

## 逐字项与语义项

```yaml
literal:
  - {text: "900 毫秒", kind: number, sentence: 1}
  - {text: "40 毫秒", kind: number, sentence: 1}
  - {text: "v2.3", kind: version, sentence: 2}
semantic:
  - {text: "仅", kind: qualifier, sentence: 2}
  - {text: "不适用于", kind: negation, sentence: 2}
```

逐字项核存在性（允许全半角与空格差异，不允许数值与单位变化）。语义项只计数并标黄。

## 分诊声明

一行，形如：

```
按技术长文处理，依据是正文含代码块；力度：改写；范围：structural；声口：不启用。要按别的体裁可以说一声。
```

## 候选清单（扫描输出）

```
| ID | 句 | 规则 | 触发 | 修法 |
|---|---|---|---|---|
| F1 | 1 | ZH-P-001 | 值得注意的是 | 删掉 |
| F2 | 1 | ZH-P-008 | 在……背景下 / 基于…… 两层前置状语 | 主干提前 |
| F3 | 3 | ZH-P-015 | 充分彰显了……精神 | 删掉，看前句事实是否完整 |
```

## 裁决表（第一次模型调用输出）

```
| ID | 裁决 | 理由 |
|---|---|---|
| F1 | 确认 | |
| F2 | 确认 | |
| F3 | 确认 | 删掉后第 1 句事实完整 |
| S1 | 新增 | 第 2 段与第 3 段可互换，缺依赖关系，建议作者确认 |
```

裁决取值：确认、排除、待确认、新增。排除必须写落在哪条通过条件。

## 补丁（第二次模型调用输出）

每行一条，句号区间在前：

```
[1] -> 我们把 p99 延迟从 900 毫秒压到了 40 毫秒。
[2] -> 只在开启 ⟦CODE-1⟧ 参数时生效，v2.3 之前的版本不适用。
[3] -> (删除)
[5-6] -> 合并后的一句。
[8] -> 拆出的第一句。 || 拆出的第二句。
```

规则：没出现的句号视为原样保留；`(删除)` 表示整句删除；`[a-b]` 表示合并；`||` 表示拆分。in-place 下不允许 `(删除)`、`[a-b]` 和 `||`。bounded 下 `(删除)` 只允许出现在待确认清单里，不直接执行。

## 台账（第二次模型调用输出）

```
| ID | 动作 | 说明 |
|---|---|---|
| F1 | 已改 | 删掉 |
| F2 | 已改 | 主干提前，背景并入次句 |
| F3 | 已改 | 整句删除，前句事实完整 |
| S1 | 保留 | 段落依赖要作者补，不替作者造 |
```

动作取值：已改、保留、待确认。缺编号即硬失败。

## 待确认删除清单（bounded 专用）

```
| 句 | 原句 | 删除理由 |
|---|---|---|
| 3 | 这一成果充分彰显了团队精益求精的工匠精神。 | 整句为价值拔高，删后信息不变，不承担过渡 |
```

## 核验报告（代码输出）

```yaml
status: fail | pass | pass_with_signals
hard_failures:
  - {kind: literal_missing, item: "40 毫秒", sentence: 1}
  - {kind: ledger_missing, id: F2}
signals:
  - {kind: qualifier_dropped, item: "仅", sentence: 2}
  - {kind: dash_added, count: 1}
rescan:
  remaining: [F4]
  introduced: []
round: 1
```

## 语义判定输入与输出

输入：每个变更块一组，含原文句号区间、原文、改文、前后各一句。

输出：

```
| 块 | 结论 | 项 | 说明 |
|---|---|---|---|
| [2] | 失真 | 条件 | "仅"被删，适用范围从"仅开启参数时"扩大到全部 |
| [5-6] | 通过 | | |
| [3] | 需作者确认 | | 删除的是价值判断，作者可能想保留 |
```

结论取值：通过、失真、需作者确认。七项：范围、条件、否定、情态、完成态、方向、强度。

## eval 用例

```yaml
id: 6
lang: zh
mode: rewrite
class: fact_preserve      # minimal_edit | fact_preserve | boilerplate | mode_axes
prompt: "这段技术说明太啰嗦了，帮我改写一下：..."
axes: {strength: rewrite, scope: structural}
must_preserve:
  - "900 毫秒"
  - "40 毫秒"
  - "--enable-cache"
  - "v2.3"
must_preserve_semantic:
  - "仅在开启参数时生效"
  - "不适用于 v2.3 之前的版本"
must_remove:
  - "值得注意的是"
  - "在当前的架构背景下"
  - "充分彰显"
must_not_add:
  - kind: first_person
  - kind: causal_marker
sentence_count: {min: 2, max: 4}
expected_verdict: null       # 审稿模式用
judge_rubric: "不得把最后一句换成另一句意义拔高的话。"
```

机械断言：must_preserve、must_remove、must_not_add、sentence_count、受保护片段、最小编辑样本的改动范围。模型判官：must_preserve_semantic、judge_rubric、自然度。CI 只阻断机械断言和判官确认的失真。

## 基线记录

```yaml
run: baseline-original
skill_version: 37e96bf
model: <模型 id>
temperature: 0
date: 2026-09-07
cases:
  - id: 6
    missed_detection: ["ZH-P-008"]
    missed_handling: []
    wrong_edit: ["40 毫秒 -> 约 40 毫秒"]
    out_of_scope: []
```
