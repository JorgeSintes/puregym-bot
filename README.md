# PureGym Bot

Single-user Telegram bot for PureGym automation.

## Setup

- Copy `config_template.yaml` to `config.yaml` at the repo root
- Fill in your Telegram and PureGym credentials in `config.yaml`
- Install dependencies:

```bash
uv sync --dev
```

By default, `puregym-mcp` is resolved from the GitHub `main` branch. If you are co-developing both repos locally, you can temporarily override that with a local editable install of your sibling `puregym-mcp` checkout.

## Run

```bash
uv run puregym-bot
```

## Test

```bash
uv run pytest
uv run python -m compileall puregym_bot tests
```

## Files

- `config.yaml`: bot runtime config
- `config_template.yaml`: template config to copy and edit
- `puregym_bot/`: bot package
- `tests/`: bot test suite
