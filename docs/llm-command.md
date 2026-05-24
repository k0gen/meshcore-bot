# Upstream-style LLM command

Local LLM replies via Ollama or LM Studio (`llm` command), configured in **`[Llm_Command]`** like `Ping_Command` or `Wx_Command`.

## Layout

| Path | Role |
|------|------|
| `modules/commands/llm_command.py` | Command plugin (`llm`, `@[bot_name]`) |
| `modules/llm/` | Client, tools, persona, mesh text helpers |
| `modules/service_plugins/radio_probe_recovery_service.py` | Optional probe-timeout restart |
| `modules/llm/persona.default.md` | Default system persona |

## Config

```ini
[Llm_Command]
enabled = false
provider = ollama
model = llama3.2
max_reply_bytes = 120
enable_tools = true
# channels =
```

See `config.ini.example` for all options.

## Triggers

- `llm <question>`
- `@[bot_name]` from `[Bot] bot_name`

## Tests

```bash
pytest tests/test_llm_*.py --no-cov
```
