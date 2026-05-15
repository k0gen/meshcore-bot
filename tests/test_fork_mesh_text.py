"""Tests for fork mesh text helpers."""

from fork.service_plugins.mesh_text import (
    extract_lm_prompt,
    split_utf8_chunks,
    truncate_to_utf8_bytes,
    utf8_byte_len,
)


def test_extract_lm_prompt() -> None:
    assert extract_lm_prompt("lm hello") == "hello"
    assert extract_lm_prompt("LM: question?") == "question?"
    assert extract_lm_prompt("lm") == "(no question)"
    assert extract_lm_prompt("!lm test", "") == "test"
    assert extract_lm_prompt("ping lm") is None


def test_truncate_utf8_bytes() -> None:
    text = "żółć"  # multi-byte
    assert utf8_byte_len(text) > 4
    out = truncate_to_utf8_bytes(text * 10, 20)
    assert utf8_byte_len(out) <= 20


def test_split_utf8_chunks() -> None:
    chunks = split_utf8_chunks("a" * 300, 100)
    assert len(chunks) >= 3
    for c in chunks:
        assert utf8_byte_len(c) <= 100
