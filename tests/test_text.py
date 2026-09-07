from engine import text as T


def test_segment_roundtrip_and_numbering():
    src = "值得注意的是，延迟从 900 毫秒降到了 40 毫秒。该优化仅在 v2.3 之后生效！\n\n第二段只有一句。"
    ss = T.segment(src)
    assert T.join(ss) == src
    assert [s.id for s in ss] == [1, 2, 3]
    assert ss[0].text == "值得注意的是，延迟从 900 毫秒降到了 40 毫秒。"
    assert ss[1].text == "该优化仅在 v2.3 之后生效！"
    assert ss[1].paragraph == 1
    assert ss[2].paragraph == 2
    assert (
        T.render_numbered(ss)
        == "[1] 值得注意的是，延迟从 900 毫秒降到了 40 毫秒。\n[2] 该优化仅在 v2.3 之后生效！\n\n[3] 第二段只有一句。"
    )


def test_decimal_and_version_not_split():
    src = "p95 延迟 3.2 秒，v2.3 之前不适用。Run it. Then wait."
    ss = T.segment(src)
    assert [s.text for s in ss] == ["p95 延迟 3.2 秒，v2.3 之前不适用。", "Run it.", "Then wait."]
    assert T.join(ss) == src


def test_closing_quote_stays_with_sentence():
    src = "他说：“行吧。”然后走了。"
    ss = T.segment(src)
    assert ss[0].text == "他说：“行吧。”"
    assert ss[1].text == "然后走了。"


def test_heading_and_placeholder_lines_are_single_sentences():
    src = "# 标题。带句号\n\n⟦BLOCK-1⟧\n\n正文。"
    ss = T.segment(src)
    assert ss[0].text == "# 标题。带句号"
    assert ss[1].text == "⟦BLOCK-1⟧" and ss[1].protected
    assert ss[2].text == "正文。"
    assert T.join(ss) == src


def test_list_item_keeps_marker_and_trailing_newlines():
    src = "- 第一点。第二句。\n- 第二点。\n"
    ss = T.segment(src)
    assert ss[0].text == "- 第一点。"
    assert ss[1].text == "第二句。"
    assert ss[2].text == "- 第二点。"
    assert T.join(ss) == src


def test_counts():
    assert T.count_cjk("中文 abc 12") == 2
    assert T.count_words("The cache, warms on boot.") == 5
    assert T.is_chinese("我们把 CI 时间压到了 6 分钟")
    assert not T.is_chinese("We cut CI time to six minutes")
