"""Step 4.5: deterministic verification.

Hard failures send the draft back to the rewrite call. Signals are recorded and
handed to the semantic judge and the report; they never block on their own.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from engine import lexicon
from engine import text as T
from engine.patch import ApplyResult, Patch, check_scope
from engine.prepare import Prepared
from engine.protect import restore
from engine.tables import LedgerRow, PendingDeletion, Verdict

LENGTH_FLOOR = 0.85  # inherited from upstream (ALL-M-019); not measured here
SENTENCE_DRIFT = 0.10

_DASH_RE = re.compile(r"—|–|(?<=\S) - (?=\S)|--")
_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
_EXCLAIM_RE = re.compile(r"[！!]")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", "", s)


@dataclass
class Report:
    status: str = "pass"  # fail | pass | pass_with_signals
    hard_failures: list[dict] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)
    rescan: dict = field(default_factory=lambda: {"remaining": [], "introduced": []})
    round: int = 1
    output_text: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def verify(
    prep: Prepared,
    applied: ApplyResult,
    patches: list[Patch],
    ledger: list[LedgerRow],
    verdicts: list[Verdict],
    pending: list[PendingDeletion],
    *,
    round_no: int = 1,
) -> Report:
    rep = Report(round=round_no)
    ax = prep.axes
    hard = rep.hard_failures
    sig = rep.signals

    # 1. patch validity (from apply)
    hard.extend(applied.failures)

    # 2. protected segments restore verbatim
    new_protected_text = T.join(applied.sentences)
    restored, prot_fail = restore(new_protected_text, prep.placeholders)
    hard.extend(prot_fail)
    rep.output_text = restored

    # 3. literal items present
    out_norm = _norm(restored)
    for it in prep.literal:
        if _norm(it.text) not in out_norm:
            hard.append({"kind": "literal_missing", "item": it.text, "sentence": it.sentence})

    # 4. ledger covers every id that needed handling
    need = {v.id for v in verdicts if v.verdict in ("确认", "待确认", "新增")}
    have = {r.id for r in ledger}
    for vid in sorted(need - have, key=_id_key):
        hard.append({"kind": "ledger_missing", "id": vid})
    for r in ledger:
        if r.action not in ("已改", "保留", "待确认"):
            hard.append({"kind": "ledger_invalid", "id": r.id, "item": r.action})

    # 5. authorization scope
    hard.extend(check_scope(patches, ax.scope, ax.strength, {p.sentence for p in pending}))
    n_old = sum(1 for s in prep.sentences if not s.protected)
    n_new = sum(1 for s in applied.sentences if not s.protected)
    if ax.scope == "in-place" and n_new != n_old:
        hard.append(
            {
                "kind": "scope_violation",
                "item": "sentence_count",
                "reason": f"in-place 句数从 {n_old} 变为 {n_new}",
            }
        )

    # ---- signals
    old_text = prep.original
    lex = lexicon.load(prep.lang)
    old_q = lexicon.count_phrases(old_text, lex["qualifiers"])
    new_q = lexicon.count_phrases(restored, lex["qualifiers"])
    if new_q < old_q:
        sig.append({"kind": "qualifier_dropped", "before": old_q, "after": new_q})
    old_n = lexicon.count_phrases(old_text, lex["negations"])
    new_n = lexicon.count_phrases(restored, lex["negations"])
    if new_n != old_n:
        sig.append({"kind": "negation_changed", "before": old_n, "after": new_n})
    old_c = lexicon.count_phrases(old_text, lex["causal_markers"])
    new_c = lexicon.count_phrases(restored, lex["causal_markers"])
    if new_c > old_c:
        sig.append({"kind": "causal_added", "before": old_c, "after": new_c})
    old_fp = lexicon.count_phrases(old_text, lex["first_person"])
    new_fp = lexicon.count_phrases(restored, lex["first_person"])
    if new_fp > old_fp:
        sig.append({"kind": "first_person_added", "before": old_fp, "after": new_fp})
    for name, rx in (
        ("dash_added", _DASH_RE),
        ("emoji_added", _EMOJI_RE),
        ("exclamation_added", _EXCLAIM_RE),
    ):
        o, nn = len(rx.findall(old_text)), len(rx.findall(restored))
        if nn > o:
            sig.append({"kind": name, "count": nn - o})
    old_len, new_len = T.length(old_text, prep.lang), T.length(restored, prep.lang)
    if old_len and new_len < old_len * LENGTH_FLOOR:
        sig.append({"kind": "length_below_floor", "before": old_len, "after": new_len})
    if (
        ax.scope in ("in-place", "bounded")
        and n_old
        and abs(n_new - n_old) > n_old * SENTENCE_DRIFT
    ):
        sig.append({"kind": "sentence_count_drift", "before": n_old, "after": n_new})

    # rescan by lexicon (phase-1 stand-in for the scanner)
    before_hits = lexicon.phrase_hits(prep.protected_text, lex["patterns"])
    after_hits = lexicon.phrase_hits(new_protected_text, lex["patterns"])
    remaining = [r for r, c in after_hits.items() if c and before_hits.get(r)]
    introduced = [r for r, c in after_hits.items() if c > before_hits.get(r, 0)]
    rep.rescan = {"remaining": remaining, "introduced": introduced}
    cleared = sum(max(0, before_hits[r] - after_hits.get(r, 0)) for r in before_hits)
    added = sum(max(0, after_hits.get(r, 0) - before_hits.get(r, 0)) for r in after_hits)
    if added > cleared:
        sig.append(
            {"kind": "rescan_introduced_more_than_cleared", "cleared": cleared, "introduced": added}
        )

    rep.status = "fail" if hard else ("pass_with_signals" if sig else "pass")
    return rep


def _id_key(vid: str) -> tuple[str, int]:
    m = re.match(r"([A-Za-z]+)(\d+)", vid)
    return (m.group(1), int(m.group(2))) if m else (vid, 0)
