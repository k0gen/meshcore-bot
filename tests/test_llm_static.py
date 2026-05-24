from modules.llm.static_replies import try_static_reply


def test_static_linux_memory() -> None:
    out = try_static_reply("how to check free memory in Linux?", 200)
    assert out is not None
    assert "free -h" in out
