# PureGym Bot

Single-user Telegram bot for PureGym automation.

## Setup

- Clone `puregym-bot` and `puregym-mcp` as sibling directories, or update the local path source in `pyproject.toml`
- Copy `config_template.yaml` to `config.yaml` at the repo root
- Fill in your Telegram and PureGym credentials in `config.yaml`
- Install dependencies:

```bash
uv sync --dev
```

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
