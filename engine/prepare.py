"""Step 4.1: gates, placeholders, numbering, literal/semantic tables, triage."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from engine import lexicon
from engine import text as T
from engine.protect import (
    PLACEHOLDER_RE,
    Placeholder,
    attach_sentences,
    find_credentials,
    is_prose_path,
    protect,
)

SHORT_TEXT_ZH = 80
SHORT_TEXT_EN = 40
ZH_LONG_TEXT = 1000

_NUMBER_RE = re.compile(
    r"(?<![0-9A-Za-z.])"
    r"(\d[\d,]*(?:\.\d+)?)"
    r"\s*"
    r"(%|％|ms|毫秒|秒|分钟|小时|天|周|个月|年|万元|元|亿|万|千|个百分点|个|条|张|笔|次|人|台|行|处|轮|倍|GB|MB|KB|TB|qps|QPS|rps)?"
    r"(?![0-9A-Za-z])",
)
_VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)*[A-Za-z]?\b|\bv\d+\b")
_DATE_RE = re.compile(
    r"\d{4}\s*年(?:\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)?|\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}-\d{2}-\d{2}|\d{1,2}\s*点\s*\d{1,2}\s*分|\b\d{1,2}:\d{2}(?:\s*UTC)?\b|Q[1-4]",
)
_BRAND_RE = re.compile(r"(?<![A-Za-z⟦-])[A-Z][A-Za-z0-9]+(?:[ -][A-Z][A-Za-z0-9]+)*(?![A-Za-z⟧])")
_HASHTAG_RE = re.compile(r"(?:^|\s)#[^\s#]+")
_STEP_RE = re.compile(
    r"^\s*(?:\d+[.、)]|第[一二三四五六七八九十\d]+步|步骤\s*\d+|Step\s*\d+)", re.MULTILINE
)
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)


@dataclass
class Item:
    text: str
    kind: str
    sentence: int


@dataclass
class Axes:
    mode: str = "rewrite"  # review | rewrite | file
    strength: str = "rewrite"  # rewrite | polish | proofread
    scope: str = "structural"  # structural | bounded | in-place
    genre: str = "通用长文"
    genre_clue: str = "无线索命中"
    voice: str = "不启用"
    short_text: bool = False
    user_specified: list[str] = field(default_factory=list)


@dataclass
class Prepared:
    lang: str
    original: str
    protected_text: str
    placeholders: list[Placeholder]
    sentences: list[T.Sentence]
    literal: list[Item]
    semantic: list[Item]
    axes: Axes
    triage_line: str
    stop_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "lang": self.lang,
            "original": self.original,
            "protected_text": self.protected_text,
            "placeholders": [asdict(p) for p in self.placeholders],
            "sentences": [asdict(s) for s in self.sentences],
            "literal": [asdict(i) for i in self.literal],
            "semantic": [asdict(i) for i in self.semantic],
            "axes": asdict(self.axes),
            "triage_line": self.triage_line,
            "stop_reason": self.stop_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Prepared:
        return cls(
            lang=d["lang"],
            original=d["original"],
            protected_text=d["protected_text"],
            placeholders=[Placeholder(**p) for p in d["placeholders"]],
            sentences=[T.Sentence(**s) for s in d["sentences"]],
            literal=[Item(**i) for i in d["literal"]],
            semantic=[Item(**i) for i in d["semantic"]],
            axes=Axes(**d["axes"]),
            triage_line=d["triage_line"],
            stop_reason=d.get("stop_reason"),
        )

    def numbered(self) -> str:
        return T.render_numbered(self.sentences)


# ---------------------------------------------------------------- tables


def extract_literal(sentences: list[T.Sentence]) -> list[Item]:
    items: list[Item] = []
    seen: set[tuple[str, int]] = set()

    def add(txt: str, kind: str, sid: int) -> None:
        key = (txt, sid)
        if txt and key not in seen:
            seen.add(key)
            items.append(Item(text=txt, kind=kind, sentence=sid))

    for s in sentences:
        if s.protected:
            continue
        body = PLACEHOLDER_RE.sub(" ", s.text)
        for m in _DATE_RE.finditer(body):
            add(m.group(0).strip(), "date", s.id)
        for m in _VERSION_RE.finditer(body):
            add(m.group(0), "version", s.id)
        for m in _NUMBER_RE.finditer(body):
            num, unit = m.group(1), m.group(2) or ""
            add((num + " " + unit).strip() if unit else num, "number", s.id)
        for m in _BRAND_RE.finditer(body):
            tok = m.group(0)
            if (len(tok) >= 2 and not tok.isupper()) or len(tok) >= 3:
                add(tok, "name", s.id)
    return items


def extract_semantic(sentences: list[T.Sentence], lang: str) -> list[Item]:
    lex = lexicon.load(lang)
    items: list[Item] = []
    for s in sentences:
        if s.protected:
            continue
        for q in lex["qualifiers"]:
            for _ in range(s.text.count(q)):
                items.append(Item(text=q, kind="qualifier", sentence=s.id))
        for ng in lex["negations"]:
            for _ in range(s.text.count(ng)):
                items.append(Item(text=ng, kind="negation", sentence=s.id))
    return items


# ---------------------------------------------------------------- triage

_REVIEW_WORDS = (
    "看看",
    "是不是 AI",
    "是不是AI",
    "哪里像",
    "审一遍",
    "审稿",
    "有什么问题",
    "要不要改",
    "帮我看",
)
_PROOFREAD_WORDS = ("校对", "只改错字", "错别字")
_POLISH_WORDS = ("润色", "顺一下", "通顺")
_INPLACE_WORDS = (
    "一句都别删",
    "一句也别删",
    "句子数量",
    "保留句数",
    "完全原样",
    "一句不删",
    "句数不变",
)
_BOUNDED_WORDS = ("别删句", "不要删句", "不要合并", "别合并")
_PUBLIC_WORDS = ("公众号", "发在", "发布", "对外", "博客", "专栏")
_BUSINESS_WORDS = ("融资", "投资", "估值", "轮", "尊敬的", "Dear", "raise", "funding")
_SALUTATION_RE = re.compile(r"^(?:尊敬的|亲爱的|Hi|Hello|Dear)\b", re.MULTILINE)


def infer_axes(
    user_request: str, body: str, protected_text: str, lang: str, *, file_path: str | None = None
) -> Axes:
    ax = Axes()
    req = user_request or ""
    # mode
    if file_path:
        ax.mode = "file"
    elif any(w in req for w in _REVIEW_WORDS) and not any(
        w in req for w in ("改写", "重写", "润色", "去 AI", "去AI", "改一下", "改得", "改成")
    ):
        ax.mode = "review"
    # strength
    if any(w in req for w in _PROOFREAD_WORDS):
        ax.strength = "proofread"
        ax.user_specified.append("strength")
    elif any(w in req for w in _POLISH_WORDS):
        ax.strength = "polish"
        ax.user_specified.append("strength")
    # scope
    n = T.length(body, lang)
    if any(w in req for w in _INPLACE_WORDS):
        ax.scope = "in-place"
        ax.user_specified.append("scope")
    elif any(w in req for w in _BOUNDED_WORDS):
        ax.scope = "bounded"
        ax.user_specified.append("scope")
    elif lang == "zh" and n >= ZH_LONG_TEXT:
        ax.scope = "bounded"
    # genre by form clues (ALL-PROC-053)
    words = T.count_words(body) if lang == "en" else T.count_cjk(body)
    has_code = "⟦BLOCK-" in protected_text or "⟦CODE-" in protected_text
    if words < 300 and _HASHTAG_RE.search(body):
        ax.genre, ax.genre_clue = "社交帖", "不到 300 词且带话题标签"
    elif has_code:
        ax.genre, ax.genre_clue = "技术长文", "正文含代码块或行内代码"
    elif _SALUTATION_RE.search(body) and any(w in body for w in _BUSINESS_WORDS):
        ax.genre, ax.genre_clue = "商务邮件", "有称呼加募资措辞"
    elif len(_STEP_RE.findall(body)) >= 2 or len(_HEADING_RE.findall(body)) >= 2:
        ax.genre, ax.genre_clue = "文档", "分步说明或 README 结构"
    # short text threshold (ALL-M-003)
    ax.short_text = n < (SHORT_TEXT_ZH if lang == "zh" else SHORT_TEXT_EN)
    return ax


STRENGTH_ZH = {"rewrite": "改写", "polish": "润色", "proofread": "校对"}
MODE_ZH = {"review": "审稿", "rewrite": "改写", "file": "就地改文件"}


def triage_line(ax: Axes) -> str:
    return (
        f"按{ax.genre}处理，依据是{ax.genre_clue}；模式：{MODE_ZH[ax.mode]}；"
        f"力度：{STRENGTH_ZH[ax.strength]}；范围：{ax.scope}；声口：{ax.voice}。要按别的体裁可以说一声。"
    )


# ---------------------------------------------------------------- entry


def prepare(body: str, user_request: str = "", *, file_path: str | None = None) -> Prepared:
    lang = "zh" if T.is_chinese(body) else "en"
    stop = None
    if file_path and not is_prose_path(file_path):
        stop = f"{file_path} 不是散文文件，散文改写会破坏它的结构，这个文件不改。"
    creds = find_credentials(body)
    if creds:
        stop = "输入里有疑似凭证，请删除或替换后重试。"
    prot = protect(body)
    sentences = T.segment(prot.text)
    attach_sentences(prot.placeholders, sentences)
    literal = extract_literal(sentences)
    semantic = extract_semantic(sentences, lang)
    ax = infer_axes(user_request, body, prot.text, lang, file_path=file_path)
    return Prepared(
        lang=lang,
        original=body,
        protected_text=prot.text,
        placeholders=prot.placeholders,
        sentences=sentences,
        literal=literal,
        semantic=semantic,
        axes=ax,
        triage_line=triage_line(ax),
        stop_reason=stop,
    )
