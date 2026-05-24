"""Tests for LLM mesh text helpers."""

from modules.llm.mesh_text import fit_mesh_reply, utf8_byte_len, utf8_safe_prefix


def test_utf8_safe_prefix_keeps_polish_chars() -> None:
    text = "Dzięki temu każdy węzeł działa."
    chunk = utf8_safe_prefix(text, 25)
    chunk.encode("utf-8")


def test_fit_mesh_reply_single_chunk() -> None:
    long = "MeshCore to sieć. " * 20
    chunks = fit_mesh_reply(long, 120, max_chunks=1)
    assert len(chunks) == 1
    assert utf8_byte_len(chunks[0]) <= 120


def test_fit_mesh_reply_at_most_two_chunks() -> None:
    long = "Word " * 80
    chunks = fit_mesh_reply(long, 120, max_chunks=2)
    assert len(chunks) <= 2
