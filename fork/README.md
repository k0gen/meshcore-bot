# Fork extensions (local LLM)

Experimental **AI auto-reply** for MeshCore, kept outside `modules/` so `main` can track upstream with small diffs.

## Setup

1. In main `config.ini`:

   ```ini
   [Bot]
   local_dir_path = fork
   ```

2. Copy plugin config:

   ```bash
   cp fork/config.ini.example fork/config.ini
   # Edit fork/config.ini — set enabled = true when ready
   ```

3. Run Ollama or LM Studio with an OpenAI-compatible API.

4. Restart the bot.

## Configuration

| Key | Description |
|-----|-------------|
| `provider` | `ollama` or `openai_compatible` (LM Studio, llama.cpp server, etc.) |
| `base_url` | API root, e.g. `http://127.0.0.1:11434/v1` |
| `model` | Model id (Ollama model name or LM Studio model id) |
| `trigger_keywords` | Comma-separated mesh keywords that request an LLM reply (default: `ai`) |
| `max_reply_length` | Truncate mesh replies (default 200) |

## Status

- Health check on start (lists models when possible).
- LLM client and service skeleton are in place.
- **Automatic mesh replies** are not wired yet — next step is hooking channel/DM events with rate limits and opt-in keywords.

Field-test on branch `dev` before proposing upstream changes.
