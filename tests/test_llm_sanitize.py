from modules.llm.sanitize import looks_like_reasoning_leak, sanitize_llm_reply
from modules.llm.tools import ToolContext, try_direct_tool_reply


def test_sanitize_strips_thinking_process() -> None:
    raw = "Thinking Process: 1. **Analyze the Request:** The user asked..."
    assert sanitize_llm_reply(raw) == ""


def test_direct_weather_reply() -> None:
    tool = ToolContext("weather", "Weather (City):\n12°C, wind 15 km/h")
    out = try_direct_tool_reply(tool, 120)
    assert out is not None
    assert "12" in out


def test_reasoning_leak_detected() -> None:
    assert looks_like_reasoning_leak("Identify the Tool/Action: simulate gwx")
