# PureGym Bot

Single-user Telegram bot for PureGym automation.

## Setup

- Copy `config_template.yaml` to `config.yaml` inside `puregym_bot/`
- Fill in your Telegram and PureGym credentials
- Install workspace dependencies from the repo root:

```bash
uv sync --all-packages --all-groups
```

## Run

From the workspace root:

```bash
uv run --package puregym-bot puregym-bot
```

## Files

- `config.yaml`: bot runtime config
- `config_template.yaml`: template config to copy and edit
