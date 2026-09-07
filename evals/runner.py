"""Eval runner: mechanical assertions on pipeline output (03-formats.md).

    uv run python -m evals.runner --out evals/runs/proto-1 [--model claude-sonnet-5]
    uv run python -m evals.runner --replay-dir evals/runs/recorded   # offline

Model-judged fields (must_preserve_semantic, judge_rubric, naturalness) are
copied into the result for a human or a judge model to fill in; they never
decide pass/fail here.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import yaml

from engine import lexicon, pipeline
from engine import text as T
from engine.prepare import prepare

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
_DASH_RE = re.compile(r"—|–|--")
_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def _strip_punct(s: str) -> str:
    return _PUNCT_RE.sub("", unicodedata.normalize("NFKC", s))


def load_cases(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        with p.open(encoding="utf-8") as f:
            out.append(yaml.safe_load(f))
    return sorted(out, key=lambda c: c["id"])


def check(case: dict, res: pipeline.RunResult, lang: str) -> list[dict]:
    body = case["body"]
    out = res.output_text
    report = res.report_text
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    if case.get("mode") == "review":
        add("mode_is_review", res.mode == "review", res.mode)
        if case.get("expected_verdict"):
            add("expected_verdict", case["expected_verdict"] in report, case["expected_verdict"])
        for s in case.get("forbidden_in_report", []) or []:
            add(f"forbidden_in_report:{s}", s not in report)
        add("no_rewrite_delivered", out == "")
        return checks

    add(
        "delivered",
        bool(out) and not res.stop_reason,
        res.stop_reason or res.verify.status if res.verify else "",
    )
    if not out:
        return checks
    on = _norm(out)
    for s in case.get("must_preserve", []) or []:
        add(f"must_preserve:{s}", _norm(s) in on)
    for s in case.get("must_remove", []) or []:
        add(f"must_remove:{s}", s not in out)
    for s in case.get("forbidden_in_output", []) or []:
        add(f"forbidden_in_output:{s}", s not in out)
    lex = lexicon.load(lang)
    for item in case.get("must_not_add", []) or []:
        kind = item["kind"]
        if kind == "first_person":
            ok = lexicon.count_phrases(out, lex["first_person"]) <= lexicon.count_phrases(
                body, lex["first_person"]
            )
        elif kind == "causal_marker":
            ok = lexicon.count_phrases(out, lex["causal_markers"]) <= lexicon.count_phrases(
                body, lex["causal_markers"]
            )
        elif kind == "emoji":
            ok = len(_EMOJI_RE.findall(out)) <= len(_EMOJI_RE.findall(body))
        elif kind == "dash":
            ok = len(_DASH_RE.findall(out)) <= len(_DASH_RE.findall(body))
        elif kind == "number":
            nums_in = set(re.findall(r"\d[\d,.]*", body))
            ok = set(re.findall(r"\d[\d,.]*", out)) <= nums_in
        else:
            ok = True
        add(f"must_not_add:{kind}", ok)
    sc = case.get("sentence_count")
    if sc:
        n = sum(1 for s in T.segment(out) if not s.protected)
        add("sentence_count", sc["min"] <= n <= sc["max"], str(n))
    for first, second in case.get("order", []) or []:
        i, j = out.find(first), out.find(second)
        add(f"order:{first}<{second}", i != -1 and j != -1 and i < j)
    if case.get("length_ratio_min"):
        r = T.length(out, lang) / max(1, T.length(body, lang))
        add("length_ratio_min", r >= case["length_ratio_min"], f"{r:.2f}")
    if case.get("class") == "minimal_edit":
        a, b = _strip_punct(body), _strip_punct(out)
        tol = case.get("minimal_edit_tolerance", 0.0)
        if tol:
            import difflib

            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            add("minimal_edit", ratio >= 1 - tol, f"similarity {ratio:.3f}")
        else:
            add("minimal_edit", a == b, "non-punctuation change" if a != b else "")
    if res.verify is not None:
        add("no_hard_failures", res.verify.status != "fail")
        add("not_partial", not res.partial)
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--only", nargs="*", type=int)
    ap.add_argument(
        "--out", type=Path, default=ROOT / "runs" / datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    )
    ap.add_argument("--model", default=None)
    ap.add_argument(
        "--replay-dir",
        type=Path,
        default=None,
        help="dir with <case id>/{diagnose,rewrite-r1,judge}.out.md",
    )
    ap.add_argument("--label", default="prototype")
    a = ap.parse_args(argv)

    cases = load_cases(sorted(a.cases.glob("*.yaml")))
    if a.only:
        cases = [c for c in cases if c["id"] in set(a.only)]
    a.out.mkdir(parents=True, exist_ok=True)
    results = []
    for case in cases:
        cid = case["id"]
        workdir = a.out / f"case-{cid}"
        if a.replay_dir:
            rd = a.replay_dir / f"case-{cid}"
            files = sorted(rd.glob("*.out.md"))
            backend: pipeline.Backend = pipeline.Replay(
                [p.read_text(encoding="utf-8") for p in files]
            )
        else:
            backend = pipeline.ClaudeCli(model=a.model)
        try:
            res = pipeline.run(case["body"], case["request"], backend, workdir)
        except Exception as e:  # noqa: BLE001
            results.append({"id": cid, "error": str(e), "checks": []})
            print(f"case {cid}: ERROR {e}")
            continue
        lang = prepare(case["body"]).lang
        checks = check(case, res, lang)
        failed = [c for c in checks if not c["pass"]]
        results.append(
            {
                "id": cid,
                "class": case.get("class"),
                "rounds": res.rounds,
                "status": "pass" if not failed else "fail",
                "failed": [c["check"] for c in failed],
                "signals": [s["kind"] for s in res.verify.signals] if res.verify else [],
                "judge": [
                    {"block": j.block, "result": j.result, "item": j.item} for j in res.judge
                ],
                "manual": {
                    "must_preserve_semantic": case.get("must_preserve_semantic"),
                    "judge_rubric": case.get("judge_rubric"),
                },
                "checks": checks,
            }
        )
        print(
            f"case {cid}: {'pass' if not failed else 'FAIL ' + ', '.join(c['check'] for c in failed)}"
        )
    summary = {
        "run": a.label,
        "date": datetime.now(tz=UTC).date().isoformat(),
        "model": a.model or ("replay" if a.replay_dir else "claude -p default"),
        "temperature": "not controllable via claude -p",
        "cases": results,
    }
    (a.out / "results.yaml").write_text(
        yaml.safe_dump(summary, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"wrote {a.out / 'results.yaml'}")
    return 0 if all(r.get("status") == "pass" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
