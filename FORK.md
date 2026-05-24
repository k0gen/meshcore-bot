# k0gen fork notes

LLM lives in upstream layout: `modules/commands/llm_command.py` + `[Llm_Command]`.

- Docs: [docs/llm-command.md](docs/llm-command.md)
- Deploy scripts: `scripts/start-bot.sh`, `scripts/install-macos-service.sh`
- Custom persona example: `persona/robotnik.md` → `Llm_Command persona_file`

Mirror upstream on `main`/`dev`; feature work on `feature/*` branches → PR into `main` on this fork.
