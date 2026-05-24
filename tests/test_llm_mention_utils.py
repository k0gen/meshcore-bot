"""Tests for LLM mention detection and prompt extraction."""

from modules.llm.mentions import (
    extract_llm_prompt,
    is_bracket_mention,
    strip_bracket_mention,
)


def test_bracket_mention_with_emoji_bot_name():
    name = "Robotnik🤖"
    text = f"@[{name}] co to jest mesh?"
    assert is_bracket_mention(text, name)
    assert strip_bracket_mention(text, name) == "co to jest mesh?"


def test_bracket_mention_case_insensitive():
    assert is_bracket_mention("@[testbot] hi", "TestBot")
    assert strip_bracket_mention("@[testbot] hi", "TestBot") == "hi"


def test_extract_llm_keyword():
    assert extract_llm_prompt("llm explain mesh", keyword="llm", bot_name="Bot") == "explain mesh"


def test_extract_llm_keyword_only():
    assert extract_llm_prompt("llm", keyword="llm", bot_name="Bot") == "(no question)"


def test_extract_mention_in_content():
    name = "Robotnik🤖"
    assert extract_llm_prompt(f"@[{name}] hello", keyword="llm", bot_name=name) == "hello"


def test_extract_mention_flag_after_strip():
    assert (
        extract_llm_prompt(
            "hello",
            keyword="llm",
            bot_name="Robotnik🤖",
            bot_mention_triggered=True,
        )
        == "hello"
    )


def test_no_trigger_returns_none():
    assert extract_llm_prompt("ping", keyword="llm", bot_name="Bot") is None


def test_mention_at_end_of_sentence():
    name = "Robotnik🤖"
    text = f"jaka jest pogoda? @[{name}]"
    assert extract_llm_prompt(text, keyword="llm", bot_name=name) == "jaka jest pogoda?"
