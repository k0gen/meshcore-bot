# Fork development (k0gen/meshcore-bot)

This repository is a **fork** of [agessaman/meshcore-bot](https://github.com/agessaman/meshcore-bot). Upstream owns core bot behaviour; this fork adds **local LLM integration** (Ollama, LM Studio) under `fork/` without forking the whole codebase.

## Remotes

| Remote     | URL                                              | Use |
|-----------|---------------------------------------------------|-----|
| `origin`  | `https://github.com/k0gen/meshcore-bot.git`       | Your fork — push here |
| `upstream`| `https://github.com/agessaman/meshcore-bot.git`   | Official source — pull/merge only |

One-time setup:

```bash
./scripts/fork-remotes.sh
```

## Branch strategy

| Branch | Purpose |
|--------|---------|
| `main` | Track upstream `main` + minimal fork-only files (`FORK.md`, `fork/`, `scripts/sync-upstream.sh`, CI guard for docs). Rebase or merge from `upstream/main` often. |
| `dev`  | AI features, field tests, Docker images tagged `dev`. Open PRs to upstream from here when stable. |

Stay current with upstream:

```bash
./scripts/sync-upstream.sh          # merge upstream/main into current branch
./scripts/sync-upstream.sh --rebase # or rebase (cleaner history, more conflict risk)
```

## Docker images (CI)

Workflow [`.github/workflows/docker-build.yml`](.github/workflows/docker-build.yml) uses `ghcr.io/${{ github.repository }}`, so pushes to **this fork** publish:

- `ghcr.io/k0gen/meshcore-bot:latest` — branch `main`
- `ghcr.io/k0gen/meshcore-bot:dev` — branch `dev`
- `ghcr.io/k0gen/meshcore-bot:sha-<commit>` — every build

After the first successful workflow run:

1. **Settings → Actions → General** — enable workflows if they were disabled on the fork.
2. **Packages** — open the new `meshcore-bot` package → **Package settings** → set visibility to **Public** (or authenticate `docker login ghcr.io` for private pulls).
3. **Settings → Actions → General → Workflow permissions** — *Read and write* (needed for GHCR push).

Local deploy: copy [`fork.env.example`](fork.env.example) to `.env` or run `./docker-setup.sh` (auto-detects `k0gen` in `origin` URL).

```bash
docker pull ghcr.io/k0gen/meshcore-bot:latest
# or
docker compose up -d --build
```

## AI / local LLM (experimental)

Code lives under [`fork/`](fork/) and loads via the standard local-plugin path (no core patches):

```ini
[Bot]
local_dir_path = fork
```

Copy [`fork/config.ini.example`](fork/config.ini.example) into `fork/config.ini` and enable `[AI_Reply]`. Backends:

- **Ollama** — `http://127.0.0.1:11434/v1` (OpenAI-compatible)
- **LM Studio** — local server URL from LM Studio (typically port 1234)

See [`fork/README.md`](fork/README.md) for configuration and roadmap.

## What to avoid merging upstream

Keep fork-specific paths out of upstream PRs unless agreed:

- `FORK.md`, `fork.env.example`, `fork/**`, `scripts/fork-remotes.sh`, `scripts/sync-upstream.sh`
- The `if: github.repository == 'agessaman/meshcore-bot'` guard in `docs.yml` (harmless on upstream)

## Upstream PR (later)

When field tests are done:

1. Rebase `dev` onto latest `upstream/main`.
2. Move stable AI code from `fork/` into `modules/` only if upstream wants it in-tree; otherwise document `local_dir_path` + ship plugin as optional add-on.
3. Open PR to `agessaman/meshcore-bot:dev` with tests and docs.
