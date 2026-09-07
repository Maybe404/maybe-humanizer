# evals/

- `cases/`：结构化用例，schema 见 doc/03-formats.md。阶段 1 只覆盖中文，从前一版 26 条里转出 17 条（1、2、5、6、9、10、13、14、15、16、17、18、19、20、21、22、26），id 沿用。每条把用户原话拆成 `request` 和 `body` 两个字段，机械断言字段是 `must_preserve`、`must_remove`、`must_not_add`、`forbidden_in_output`、`sentence_count`、`order`、`length_ratio_min`、`minimal_edit_tolerance`；`must_preserve_semantic` 和 `judge_rubric` 留给模型判官或人。
- `holdout/`：留出样本，不参与开发调试。基线和每个阶段都在同一批上跑。
- `runner.py`：跑流水线并做机械断言。`uv run python -m evals.runner --out evals/runs/<名字>`；离线用 `--replay-dir` 回放录好的模型输出。
- `baselines/`：两份基线记录（原版、修正版）。格式见 doc/03-formats.md「基线记录」。

CI 阻断项只包括机械断言和判官确认的失真；自然度、复核信号、成本与轮数只记录。
