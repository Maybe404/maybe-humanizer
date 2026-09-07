"""Apply the phase-0 contract fixes (doc/04-phase0-contract-fixes.md) to the previous skill repo.

    uv run python scripts/phase0_fixes.py [--repo /Users/maybe/code/github.com/Maybe404/skill] [--check]

Each fix is an exact old->new replacement so the change is reviewable and
repeatable. ``--check`` only reports which fixes are still pending. The
SOURCES.md generator bug (doc/04 section 5, ai-zixun author field) is not
covered here: it needs the generator script located first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL = "skills/maybe-humanizer"

FIXES: list[tuple[str, str, str, str]] = [
    # (label, relative path, old, new)
    (
        "1 ALL-PROC-053 判据段：无线索时落默认档",
        f"{SKILL}/references/process.md",
        "一条线索都不命中时不落到默认档，按 ALL-PROC-003 停下来问一个具体问题，这条 excepts 记在本条一端。",
        "一条线索都不命中时落到通用长文默认档（ALL-G-007），输出开头写明「按通用长文处理」，供用户覆盖；只在体裁会改变保护决定（疑似虚构文本、疑似凭证）时才按 ALL-PROC-003 问一句。",
    ),
    (
        "1 genres.md 开头",
        f"{SKILL}/references/genres.md",
        "分诊时先过这里（ALL-PROC-001），体裁定不下来时按 ALL-PROC-003 问一句，不猜。",
        "分诊时先过这里（ALL-PROC-001），体裁按 ALL-PROC-053 的形式线索判定，一条线索都不命中时落通用长文默认档并在输出开头写明，供用户覆盖；只在体裁会改变保护决定（疑似虚构、疑似凭证）时才按 ALL-PROC-003 问一句。",
    ),
    (
        "1 ALL-G-002 通过条件",
        f"{SKILL}/references/genres.md",
        "**通过条件。** 体裁不明时按 ALL-PROC-003 先问，不猜。用户没有点名要叠体例层时",
        "**通过条件。** 体裁不明时按 ALL-PROC-053 的形式线索判定，一条都不命中时落通用长文默认档并写明，不提问；只在体裁会改变保护决定（疑似虚构、疑似凭证）时才按 ALL-PROC-003 问一句。用户没有点名要叠体例层时",
    ),
    (
        "2 ALL-PROC-001 判据：四件事推断不问",
        f"{SKILL}/references/process.md",
        "四件事里有任何一件填不出来，按 ALL-PROC-003 去问，不许填一个推测值当作已知。",
        "四件事按形式线索（ALL-PROC-053）和用户措辞推断，推断结果写进这一行，标明是推断，供用户覆盖；不因为某一件推断不出来就停下来问，提问的两种触发条件在 ALL-PROC-003。",
    ),
    (
        "2 ALL-PROC-001 反例",
        f"{SKILL}/references/process.md",
        "- 反例：读完一篇论点模糊的稿子，判断不出它要达到什么目的，既不去问用户，也不写这一行，按自己猜的重点开始调结构。违反点：四件事没有落到纸面，目的那一格是猜的。",
        "- 反例：读完一篇论点模糊的稿子，不写这一行，按自己猜的重点开始调结构。违反点：四件事没有落到纸面，用户无从覆盖。",
    ),
    (
        "2 ALL-PROC-003 判据：触发条件收窄为两种",
        f"{SKILL}/references/process.md",
        "**判据。** 受众、发布渠道或目的三项里有一项定不下来时停手提问，一次只发一个问题。问题的内容限定在两种：这篇给谁看、发在哪里；读者读完应该想什么、感受什么、做什么。数问号，超过一个即违反。不问就自行补出品牌主体、渠道或语体，同样违反。",
        "**判据。** 只有两种情况停手提问：一、正文的意思读不明白，且读不明白的那部分会影响事实、指代或论证关系（ALL-PROC-004 的情形）；二、体裁会改变保护决定，即疑似虚构文本（ALL-G-003）或疑似凭证（ALL-PROT-011）。其余情况不问：受众、渠道、目的、语体按 ALL-PROC-001 推断并在分诊那一行标明，供用户覆盖。提问时一次只发一个问题，数问号，超过一个即违反。",
    ),
    (
        "2 ALL-PROC-003 通过条件：体裁由 053 判定",
        f"{SKILL}/references/process.md",
        "**通过条件。** 体裁命中 ALL-PROC-053 的形式线索时不走本条，按那条判定并声明判定依据。无源引用的处理力度不明时也不走本条，按 ALL-PROC-040 取保守的 audit-only；那条在自己一端记了 excepts，分域是：本条问的是这篇写给谁看，那条定的是这一条论断怎么办。",
        "**通过条件。** 体裁由 ALL-PROC-053 判定，不走本条；一条线索都不命中时落通用长文默认档并写明，仍不走本条。无源引用的处理力度不明时也不走本条，按 ALL-PROC-040 取保守的 audit-only；那条在自己一端记了 excepts，分域是：本条定什么时候停下来问，那条定这一条论断怎么办。",
    ),
    (
        "2 ALL-PROC-003 已知会漏掉什么与正反例",
        f"{SKILL}/references/process.md",
        "**已知会漏掉什么。** 一个问题问不全时本条没有出口，只能等用户答完再问第二轮，多轮提问的次数上限本条不管。\n\n- 正例：用户贴了一段介绍性文字没说发在哪里，回一句「这段发在哪个渠道」，稿子不动。\n- 反例：同一段文字，一次抛出四个问题（给谁看、发在哪、正式还是随意、有没有字数限制）；或者不问，直接假定这是品牌官网文案并按官网语体改。违反点：前者超过一个问题，后者替用户补出了渠道和语体。",
        "**已知会漏掉什么。** 推断出来的受众和目的可能是错的，本条把纠错交给用户覆盖，不在动手前拦。一个问题问不全时本条没有出口，只能等用户答完再问第二轮。\n\n- 正例：遇到一处指代不清且影响事实，回一句「这句里的『它』指产品还是团队」，稿子不动；用户贴了一段介绍性文字没说发在哪里，按形式线索推断成通用长文，在分诊那一行写明，直接改。\n- 反例：因为用户没说发在哪里就停下来问「这段发在哪个渠道」；或者一次抛出四个问题。违反点：前者不在两种触发条件之内，后者超过一个问题。",
    ),
    (
        "2 SKILL.md 分诊开头",
        f"{SKILL}/SKILL.md",
        "先过五个问题。答不出来的按 ALL-PROC-003 问一句，一次只问一个，不猜。",
        "先过五个问题。只在两种情况下按 ALL-PROC-003 问一句：意思读不明白且影响事实或指代；体裁会改变保护决定（疑似虚构、疑似凭证）。其余答不出来的按形式线索和用户措辞推断，写进分诊那一行供用户覆盖，一次只问一个。",
    ),
    (
        "2 SKILL.md 分诊第 5 条",
        f"{SKILL}/SKILL.md",
        "5. **体裁、读者、目的、语体。**四件事写成一行记下来（ALL-PROC-001），后面每一处改动都要对得上它。",
        "5. **体裁、读者、目的、语体。**四件事按形式线索和用户措辞推断，写成一行记下来并标明是推断（ALL-PROC-001），供用户覆盖，后面每一处改动都要对得上它。",
    ),
    (
        "3 SKILL.md description：校对是最低一档",
        f"{SKILL}/SKILL.md",
        "不用于翻译、从零写作、只查错别字、繁体中文，也不判断一段文字是不是 AI 写的、不打 AI 概率分、不协助规避披露规定。",
        "校对是最低一档力度，只改错字病句。不用于翻译、从零写作、繁体中文，也不判断一段文字是不是 AI 写的、不打 AI 概率分、不协助规避披露规定。",
    ),
    (
        "3 SKILL.md 分诊第 2 条",
        f"{SKILL}/SKILL.md",
        "2. **是不是这个 skill 的活。**翻译、从零写作、只查错别字、繁体中文、未经授权替真人换声口都不做（ALL-G-001）。",
        "2. **是不是这个 skill 的活。**翻译、从零写作、繁体中文、未经授权替真人换声口都不做（ALL-G-001）；校对是最低一档力度，做。",
    ),
    (
        "3 ALL-G-001 不适用四类",
        f"{SKILL}/references/genres.md",
        "两者都包括段落、文章和长文的结构重写。不适用的有五类：翻译、从零写作、只查错别字、繁体中文、未经授权替真人更换声口。",
        "两者都包括段落、文章和长文的结构重写，也包括 ALL-PROC-005 最低一档的校对（只改错字病句和明确错误）。不适用的有四类：翻译、从零写作、繁体中文、未经授权替真人更换声口。",
    ),
    (
        "4 SKILL.md 自查第 6 条补出口",
        f"{SKILL}/SKILL.md",
        "说不出这一遍在句长或段长上动了哪一处就退回改写。\n\n轮数上限三轮",
        "说不出这一遍在句长或段长上动了哪一处就退回改写。原文句长段长本来就有变化的，写明「原文本来就有变化，本遍未改」即通过，不为满足指标再改一轮（ALL-PROC-029、ALL-PROC-056）。\n\n轮数上限三轮",
    ),
    (
        "5 ALL-PROC-024 结论措辞",
        f"{SKILL}/references/process.md",
        "用四种判定之一：命中 AI 高频写作模式、真人文本（停手）、真人文本（已授权改写）、不确定。证据最多列两条具体结构，不对作者身份下结论。",
        "用四种判定之一：命中模式 N 处、无需编辑（停手）、已授权改写、不确定。证据最多列两条具体结构，不对作者身份下结论；结论的措辞里不出现「AI」「真人」这类会被读成作者身份判断的词。",
    ),
    (
        "5 ALL-PROC-024 正例",
        f"{SKILL}/references/process.md",
        "- 正例：「判断：命中 AI 高频写作模式。证据：",
        "- 正例：「判断：命中模式 2 处。证据：",
    ),
    (
        "5 SKILL.md 审稿结论措辞",
        f"{SKILL}/SKILL.md",
        "结论用四种判定之一（ALL-PROC-024）：命中 AI 高频写作模式、真人文本（停手）、真人文本（已授权改写）、不确定。",
        "结论用四种判定之一（ALL-PROC-024）：命中模式 N 处、无需编辑（停手）、已授权改写、不确定。",
    ),
    (
        "5 EN-P-001 标题",
        f"{SKILL}/references/patterns-en.md",
        "### EN-P-001 AI 高频词一律不用",
        "### EN-P-001 AI 高频词表",
    ),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo", type=Path, default=Path("/Users/maybe/code/github.com/Maybe404/skill")
    )
    ap.add_argument("--check", action="store_true", help="report pending fixes, change nothing")
    a = ap.parse_args(argv)
    pending = applied = 0
    for label, rel, old, new in FIXES:
        path = a.repo / rel
        text = path.read_text(encoding="utf-8")
        if new in text and old not in text:
            print(f"done     {label}")
            applied += 1
            continue
        if old not in text:
            print(f"MISSING  {label}: old text not found in {rel}")
            pending += 1
            continue
        if text.count(old) != 1:
            print(f"AMBIG    {label}: old text appears {text.count(old)} times in {rel}")
            pending += 1
            continue
        if a.check:
            print(f"pending  {label}")
            pending += 1
            continue
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"applied  {label}")
        applied += 1
    print(f"{applied} applied/done, {pending} pending")
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
