"""``humanizer`` command line.

Two ways to use it:

- ``humanizer run`` drives all three model calls through a backend (default:
  the local ``claude -p``).
- Step commands (``prepare``, ``prompt``, ``apply``, ``finish``) let a host
  model do the calls itself and hand outputs back for mechanical checks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from engine import pipeline, rules, tables
from engine.prepare import Prepared, prepare


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _load_prep(workdir: Path) -> Prepared:
    return Prepared.from_dict(json.loads((workdir / "prepared.json").read_text(encoding="utf-8")))


def _load_verdicts(workdir: Path) -> list[tables.Verdict]:
    out = workdir / "diagnose.out.md"
    if not out.exists():
        return []
    return tables.parse_verdicts(
        tables.sections(out.read_text(encoding="utf-8")).get("VERDICT", "")
    )


def cmd_prepare(a: argparse.Namespace) -> int:
    body = _read(a.input)
    prep = prepare(body, a.request or "", file_path=a.input if a.file_mode else None)
    a.workdir.mkdir(parents=True, exist_ok=True)
    (a.workdir / "prepared.json").write_text(
        json.dumps(prep.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if prep.stop_reason:
        print(prep.stop_reason)
        return 2
    print(prep.triage_line)
    print()
    print(prep.numbered())
    return 0


def cmd_prompt(a: argparse.Namespace) -> int:
    prep = _load_prep(a.workdir)
    if a.step == "diagnose":
        text = pipeline.build_diagnose_prompt(prep)
        (a.workdir / "diagnose.prompt.md").write_text(text, encoding="utf-8")
    elif a.step == "rewrite":
        verdicts = _load_verdicts(a.workdir)
        failures = None
        prev = None
        if a.round > 1:
            vpath = a.workdir / f"verify-r{a.round - 1}.yaml"
            if vpath.exists():
                failures = yaml.safe_load(vpath.read_text(encoding="utf-8")).get("hard_failures")
            ppath = a.workdir / f"rewrite-r{a.round - 1}.out.md"
            if ppath.exists():
                prev = ppath.read_text(encoding="utf-8")
        text = pipeline.build_rewrite_prompt(
            prep, verdicts, failures=failures, previous_output=prev
        )
        (a.workdir / f"rewrite-r{a.round}.prompt.md").write_text(text, encoding="utf-8")
    else:
        verdicts = _load_verdicts(a.workdir)
        raw = (a.workdir / f"rewrite-r{a.round}.out.md").read_text(encoding="utf-8")
        rr = pipeline.parse_rewrite_output(prep, raw, verdicts, a.round)
        text = pipeline.build_judge_prompt(rr.applied.blocks)
        (a.workdir / "judge.prompt.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_apply(a: argparse.Namespace) -> int:
    """Verify a rewrite output; write output.md and verify-r{n}.yaml."""
    prep = _load_prep(a.workdir)
    verdicts = _load_verdicts(a.workdir)
    raw = (
        _read(a.rewrite_output)
        if a.rewrite_output
        else (a.workdir / f"rewrite-r{a.round}.out.md").read_text(encoding="utf-8")
    )
    rr = pipeline.parse_rewrite_output(prep, raw, verdicts, a.round)
    (a.workdir / f"verify-r{a.round}.yaml").write_text(
        yaml.safe_dump(rr.report.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    if rr.report.status != "fail":
        (a.workdir / "output.md").write_text(rr.report.output_text, encoding="utf-8")
    print(
        yaml.safe_dump(
            {k: v for k, v in rr.report.to_dict().items() if k != "output_text"},
            allow_unicode=True,
            sort_keys=False,
        )
    )
    return 0 if rr.report.status != "fail" else 1


def cmd_finish(a: argparse.Namespace) -> int:
    prep = _load_prep(a.workdir)
    verdicts = _load_verdicts(a.workdir)
    if prep.axes.mode == "review":
        from engine import report as R

        text = R.review_report(prep, verdicts)
    else:
        raw = (a.workdir / f"rewrite-r{a.round}.out.md").read_text(encoding="utf-8")
        rr = pipeline.parse_rewrite_output(prep, raw, verdicts, a.round)
        jpath = a.workdir / "judge.out.md"
        judge_rows = (
            tables.parse_judge(tables.sections(jpath.read_text(encoding="utf-8")).get("JUDGE", ""))
            if jpath.exists()
            else []
        )
        from engine import report as R

        partial = any(j.result == "失真" for j in judge_rows)
        text = R.rewrite_report(
            prep,
            rr.report,
            rr.ledger,
            verdicts,
            rr.pending,
            judge_rows,
            rounds=a.round,
            partial=partial,
        )
    (a.workdir / "report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    body = _read(a.input)
    backend: pipeline.Backend
    if a.replay:
        backend = pipeline.Replay([Path(p).read_text(encoding="utf-8") for p in a.replay])
    else:
        backend = pipeline.ClaudeCli(model=a.model)
    res = pipeline.run(
        body, a.request or "", backend, a.workdir, file_path=a.input if a.file_mode else None
    )
    if a.file_mode and a.write and res.output_text and not res.partial:
        Path(a.input).write_text(res.output_text, encoding="utf-8")
    if res.output_text and not a.file_mode:
        print(res.output_text)
        print()
    print(res.report_text)
    return 0 if not res.stop_reason else 2


def cmd_gen_cards(a: argparse.Namespace) -> int:  # noqa: ARG001
    for p in rules.write_cards():
        print(p)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="humanizer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="gates, placeholders, numbering, tables, triage")
    p.add_argument("input", help="file path or - for stdin")
    p.add_argument("--request", default="", help="user's wording, decides mode/strength/scope")
    p.add_argument("--workdir", type=Path, default=Path(".humanizer"))
    p.add_argument(
        "--file-mode", action="store_true", help="in-place file mode: input is the file to edit"
    )
    p.set_defaults(fn=cmd_prepare)

    p = sub.add_parser("prompt", help="build the prompt for one model step")
    p.add_argument("step", choices=["diagnose", "rewrite", "judge"])
    p.add_argument("--workdir", type=Path, default=Path(".humanizer"))
    p.add_argument("--round", type=int, default=1)
    p.set_defaults(fn=cmd_prompt)

    p = sub.add_parser("apply", help="apply + verify a rewrite output")
    p.add_argument(
        "rewrite_output",
        nargs="?",
        help="file with the model's rewrite output (default: workdir/rewrite-r{n}.out.md)",
    )
    p.add_argument("--workdir", type=Path, default=Path(".humanizer"))
    p.add_argument("--round", type=int, default=1)
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("finish", help="generate the delivery report")
    p.add_argument("--workdir", type=Path, default=Path(".humanizer"))
    p.add_argument("--round", type=int, default=1)
    p.set_defaults(fn=cmd_finish)

    p = sub.add_parser("run", help="run the whole pipeline through a model backend")
    p.add_argument("input")
    p.add_argument("--request", default="")
    p.add_argument("--workdir", type=Path, default=Path(".humanizer"))
    p.add_argument("--model", default=None)
    p.add_argument(
        "--replay", nargs="*", help="files with pre-recorded model outputs, in call order"
    )
    p.add_argument("--file-mode", action="store_true")
    p.add_argument(
        "--write", action="store_true", help="file mode: write the result back to the file"
    )
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("gen-cards", help="regenerate skill/cards from rules/")
    p.set_defaults(fn=cmd_gen_cards)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
