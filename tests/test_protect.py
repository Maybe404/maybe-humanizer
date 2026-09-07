from engine.protect import find_credentials, is_prose_path, protect, restore


def test_placeholders_cover_blocks_inline_code_urls_tables_frontmatter():
    src = (
        "---\ntitle: x\n---\n"
        "说明见 https://example.com/a?b=1 和 `--enable-cache`。\n\n"
        "```bash\nkubectl get deploy\n```\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n尾句。"
    )
    prot = protect(src)
    kinds = [p.kind for p in prot.placeholders]
    assert kinds == ["FM", "BLOCK", "TABLE", "CODE", "URL"]
    assert "kubectl" not in prot.text
    assert "--enable-cache" not in prot.text
    restored, failures = restore(prot.text, prot.placeholders)
    assert failures == []
    assert restored == src


def test_restore_reports_missing_and_duplicated_placeholders():
    src = "看 `a` 和 `b`。"
    prot = protect(src)
    text = prot.text.replace("⟦CODE-2⟧", "⟦CODE-1⟧")
    _, failures = restore(text, prot.placeholders)
    kinds = sorted(f["reason"] for f in failures)
    assert any("missing" in r for r in kinds)
    assert any("appears 2" in r for r in kinds)


def test_credential_gate():
    assert find_credentials("密钥是 sk-abcdefghijklmnopqrstuvwxyz123456") == ["openai_key"]
    assert find_credentials("API_KEY=YOUR_API_KEY 这种占位符不算") == []
    assert find_credentials("概念上讨论 token 和 API key 不算") == []
    assert "private_key" in find_credentials("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")


def test_prose_path_gate():
    assert is_prose_path("docs/onboarding.md")
    assert not is_prose_path("src/config.ts")
    assert not is_prose_path("config.yaml")
