from modules.llm.tools import extract_prefix_hex, format_prefix_chunks


def test_extract_prefix_hex_from_polish_question() -> None:
    q = "gdzie znajduje się prefix 14 zbadaj jeśli można"
    assert extract_prefix_hex(q) == "14"


def test_format_prefix_chunks_multiline() -> None:
    raw = "Prefix 14: 1 repeater (7d)\n1. SOLAR XIAO REPEATER (Kołobrzeg)"
    chunks = format_prefix_chunks(raw, 130, 2)
    assert chunks
