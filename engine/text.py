"""Sentence segmentation and counting helpers.

Sentences are numbered from 1, continuously across paragraphs. Every character of
the input is retained: ``"".join(s.text + s.sep for s in sentences)`` reproduces
the input exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Sentence-final punctuation. A Latin period only ends a sentence when followed by
# whitespace or end of line, so "3.2 秒" and "v2.3" stay intact.
_ZH_END = "。！？"
_EN_END = "!?"
_CLOSERS = "”」』）\"')]"
_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


@dataclass
class Sentence:
    id: int
    text: str
    sep: str  # whitespace that followed the sentence in the source
    paragraph: int
    protected: bool = False  # the sentence is a placeholder-only line


def _split_line(line: str) -> list[str]:
    """Split one line into sentence strings, keeping every character."""
    out: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        buf.append(ch)
        end = False
        if ch in _ZH_END or ch in _EN_END:
            end = True
        elif ch == "." and (i + 1 == n or line[i + 1].isspace()):
            # decimals and versions are never followed by whitespace, so this
            # period is sentence-final
            end = True
        if end:
            # swallow closing quotes/brackets and repeated terminal marks
            j = i + 1
            while j < n and (line[j] in _CLOSERS or line[j] in _ZH_END or line[j] in _EN_END):
                buf.append(line[j])
                j += 1
            # trailing spaces belong to this sentence; they become its separator
            while j < n and line[j] in " \t":
                buf.append(line[j])
                j += 1
            out.append("".join(buf))
            buf = []
            i = j
            continue
        i += 1
    if buf:
        out.append("".join(buf))
    return out


def segment(text: str) -> list[Sentence]:
    """Number the text sentence by sentence.

    Paragraphs are separated by blank lines. A line that is only a placeholder
    (``⟦KIND-n⟧``) or a Markdown heading is one sentence on its own.
    """
    sentences: list[Sentence] = []
    lines = text.split("\n")
    para = 1
    seen_content_in_para = False
    idx = 0
    pending_sep = ""  # whitespace (newlines/blank lines) not yet attached
    for li, line in enumerate(lines):
        is_last = li == len(lines) - 1
        nl = "" if is_last else "\n"
        if line.strip() == "":
            pending_sep += line + nl
            if seen_content_in_para:
                para += 1
                seen_content_in_para = False
            continue
        leading = len(line) - len(line.lstrip(" \t"))
        lead_ws, body = line[:leading], line[leading:]
        pending_sep += lead_ws
        if sentences:
            sentences[-1].sep += pending_sep
        pending_sep = ""
        stripped = body.rstrip(" \t")
        trail = body[len(stripped) :]
        placeholder_only = bool(re.fullmatch(r"⟦[A-Z]+-\d+⟧", stripped))
        if placeholder_only or stripped.startswith("#"):
            parts = [stripped]
        else:
            parts = _split_line(stripped)
        for k, part in enumerate(parts):
            core = part.rstrip(" \t")
            ws = part[len(core) :]
            idx += 1
            sep = ws
            if k == len(parts) - 1:
                sep += trail + nl
            sentences.append(
                Sentence(id=idx, text=core, sep=sep, paragraph=para, protected=placeholder_only)
            )
        seen_content_in_para = True
    if pending_sep and sentences:
        sentences[-1].sep += pending_sep
    elif pending_sep and not sentences:
        # whitespace-only document
        sentences.append(Sentence(id=1, text="", sep=pending_sep, paragraph=1))
    return sentences


def join(sentences: list[Sentence]) -> str:
    return "".join(s.text + s.sep for s in sentences)


def render_numbered(sentences: list[Sentence]) -> str:
    """Render ``[n] text`` lines, blank line between paragraphs."""
    out: list[str] = []
    last_para = None
    for s in sentences:
        if last_para is not None and s.paragraph != last_para:
            out.append("")
        out.append(f"[{s.id}] {s.text}")
        last_para = s.paragraph
    return "\n".join(out)


def count_cjk(text: str) -> int:
    return len(_CJK.findall(text))


def count_words(text: str) -> int:
    return len(_WORD.findall(text))


def is_chinese(text: str) -> bool:
    cjk = count_cjk(text)
    words = count_words(text)
    return cjk >= words


def length(text: str, lang: str) -> int:
    """Length by the language's own unit: CJK chars for zh, words for en."""
    return count_cjk(text) if lang == "zh" else count_words(text)
