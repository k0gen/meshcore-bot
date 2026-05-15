# Fork extensions (local LLM)

AI auto-reply for MeshCore via **Ollama** or **LM Studio** (OpenAI-compatible `/v1` API). Code lives under `fork/` so `main` can stay identical to upstream.

## Setup

1. Main `config.ini`:

   ```ini
   [Bot]
   local_dir_path = fork
   ```

2. Plugin config:

   ```bash
   cp fork/config.ini.example fork/config.ini
   ```

3. Run Ollama (`http://127.0.0.1:11434/v1`) or LM Studio (local server, often `http://127.0.0.1:1234/v1`).

4. Set `[AI_Reply] enabled = true` and restart the bot.

## Trigger

Send a message starting with **`lm`** (after optional `[Bot] command_prefix` or legacy `!`):

- `lm what is the weather like on mesh?`
- `lm` alone → model gets `(no question)`

## Channel policy

The bot uses your existing `[Channels]` settings:

- **`monitor_channels`** — channel replies only on listed channels
- **`respond_to_dms`** — enable/disable DM replies
- **`channel_keywords`** — if set, include **`lm`** in the comma-separated list

## Providers

| `provider` | Default `base_url` |
|------------|----------------------|
| `ollama` | `http://127.0.0.1:11434/v1` |
| `lm_studio` | `http://127.0.0.1:1234/v1` |
| `openai_compatible` | same as LM Studio (override with `base_url`) |

## Message length

Replies respect MeshCore UTF-8 byte limits (`CommandManager.get_max_message_length`): **158 bytes for DMs**, channel budget from firmware (username-dependent). Long answers are sent as multiple chunks with TX spacing.

## Branch

Develop on **`local-llm`**, not `main` or upstream `dev`. See [FORK.md](../FORK.md).
