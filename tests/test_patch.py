from engine import text as T
from engine.patch import apply, check_scope, parse_patches


def _sents(src: str) -> list[T.Sentence]:
    return T.segment(src)


def test_parse_patch_lines():
    block = "[1] -> 新句。\n[3] -> (删除)\n[5-6] -> 合并。\n[8] -> 甲。 || 乙。\n乱七八糟"
    patches, failures = parse_patches(block)
    assert [p.label for p in patches] == ["[1]", "[3]", "[5-6]", "[8]"]
    assert patches[1].is_delete
    assert patches[2].is_merge
    assert patches[3].is_split and patches[3].replacement == ["甲。", "乙。"]
    assert failures[0]["kind"] == "patch_invalid"


def test_apply_replace_delete_merge_split_and_renumber():
    src = "一。二。三。\n\n四。五。"
    ss = _sents(src)
    patches, _ = parse_patches("[1] -> 壹。\n[2] -> (删除)\n[4-5] -> 四五。")
    res = apply(ss, patches)
    assert res.failures == []
    assert [s.text for s in res.sentences] == ["壹。", "三。", "四五。"]
    assert [s.id for s in res.sentences] == [1, 2, 3]
    assert T.join(res.sentences) == "壹。三。\n\n四五。"
    labels = [b.label for b in res.blocks]
    assert labels == ["[1]", "[2]", "[4-5]"]
    assert res.blocks[1].after == ""
    assert res.blocks[2].before == "四。五。"
    assert res.blocks[2].context_before == "三。"


def test_apply_split_keeps_paragraph_break():
    ss = _sents("甲乙。\n\n丙。")
    patches, _ = parse_patches("[1] -> 甲。 || 乙。")
    res = apply(ss, patches)
    assert T.join(res.sentences) == "甲。乙。\n\n丙。"


def test_delete_paragraph_final_sentence_keeps_break():
    ss = _sents("甲。乙。\n\n丙。")
    patches, _ = parse_patches("[2] -> (删除)")
    res = apply(ss, patches)
    assert T.join(res.sentences) == "甲。\n\n丙。"


def test_apply_rejects_bad_ids_overlap_cross_paragraph_and_protected():
    ss = _sents("甲。乙。\n\n丙。丁。\n\n⟦BLOCK-1⟧")
    patches, _ = parse_patches("[9] -> x\n[2-3] -> w\n[1-2] -> y\n[2] -> z\n[5] -> 改了占位符")
    res = apply(ss, patches)
    reasons = [f["reason"] for f in res.failures]
    assert any("不存在" in r for r in reasons)
    assert any("重叠" in r for r in reasons)
    assert any("段落边界" in r for r in reasons)
    assert any(f["kind"] == "protected_mismatch" for f in res.failures)


def test_scope_checks():
    patches, _ = parse_patches("[1] -> (删除)\n[2-3] -> 合。\n[4] -> 甲。 || 乙。")
    inplace = check_scope(patches, "in-place", "rewrite", set())
    assert len(inplace) == 3
    bounded = check_scope(patches, "bounded", "rewrite", set())
    assert {v["item"] for v in bounded} == {"[1]", "[2-3]"}
    bounded_ok = check_scope(patches, "bounded", "rewrite", {1})
    assert {v["item"] for v in bounded_ok} == {"[2-3]"}
    proof = check_scope(patches, "structural", "proofread", set())
    assert len(proof) == 3
    assert check_scope(patches, "structural", "rewrite", set()) == []
