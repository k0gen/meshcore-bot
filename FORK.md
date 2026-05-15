# Fork development (k0gen/meshcore-bot)

Fork of [agessaman/meshcore-bot](https://github.com/agessaman/meshcore-bot). **Upstream owns `main` and `dev`.** This fork keeps them identical and develops local LLM features on a separate branch.

## Remotes

| Remote     | URL                                            | Use |
|-----------|------------------------------------------------|-----|
| `origin`  | `https://github.com/k0gen/meshcore-bot.git`    | Your fork — push here |
| `upstream`| `https://github.com/agessaman/meshcore-bot.git`| Official source — fetch/merge only |

```bash
./scripts/fork-remotes.sh
```

## Branch strategy

| Branch | Tracks | Purpose |
|--------|--------|---------|
| **`main`** | **`upstream/main` only** (no fork commits) | Fast-forward from upstream; never commit fork work here |
| **`dev`** | **`upstream/dev` only** | Same — mirror upstream integration branch |
| **`local-llm`** | `upstream/main` + fork files | AI (Ollama / LM Studio), `fork/`, CI tweak, docs |

```bash
# Update mirrors (no local changes on main/dev)
git checkout main && git fetch upstream && git reset --hard upstream/main && git push origin main
git checkout dev && git fetch upstream && git reset --hard upstream/dev && git push origin dev

# Develop AI
git checkout local-llm
./scripts/sync-upstream.sh    # merges upstream/main into local-llm
```

## Docker images (CI)

[`docker-build.yml`](.github/workflows/docker-build.yml) publishes to `ghcr.io/k0gen/meshcore-bot`:

| Tag | Branch |
|-----|--------|
| `latest` | `main` (upstream-equivalent build from fork CI) |
| `local-llm` | `local-llm` |
| `dev` | only if you push upstream-mirrored `dev` (upstream code, not AI) |

For AI builds use **`ghcr.io/k0gen/meshcore-bot:local-llm`**.

After first push: enable Actions on the fork; set the GHCR package to **Public** (or `docker login ghcr.io`).

Deploy locally: [`fork.env.example`](fork.env.example) or `./docker-setup.sh` (detects `k0gen` in `origin`).

## Local LLM

```ini
[Bot]
local_dir_path = fork
```

```bash
cp fork/config.ini.example fork/config.ini
```

Enable `[AI_Reply]`, set `provider` (`ollama` or `lm_studio`), `model`, and `base_url` if needed.

**Trigger:** `lm` — e.g. `lm what is meshcore?`  
**Policy:** Same as other bot replies — `[Channels]` `monitor_channels`, `respond_to_dms`, `channel_keywords` (add `lm` to the list if you use a channel whitelist).

See [`fork/README.md`](fork/README.md).

## Upstream PR (later)

Rebase `local-llm` onto latest `upstream/main` or `upstream/dev`, field-test, then open PR to `agessaman/meshcore-bot:dev` when ready.
