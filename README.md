# PureGym Bot

Single-user Telegram bot for PureGym automation.

## Setup

- Copy `config_template.yaml` to `config.yaml` at the repo root
- Fill in your Telegram and PureGym credentials in `config.yaml`
- Create the local data directory:

```bash
mkdir -p data
```

- Install dependencies:

```bash
uv sync --dev
```

By default, `puregym-mcp` is resolved from the GitHub `main` branch. If you are co-developing both repos locally, you can temporarily override that with a local editable install of your sibling `puregym-mcp` checkout.

## Run

```bash
uv run puregym-bot
```

The bot stores its SQLite state in `data/puregym_bot.db`.

## Docker

The container expects:

- `config.yaml` mounted at `/app/config.yaml`
- persistent bot data mounted at `/app/data`

Build the image locally:

```bash
docker build -t puregym-bot .
```

Run it directly:

```bash
mkdir -p data
docker run -d \
  --name puregym-bot \
  --restart unless-stopped \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  -v "$(pwd)/data:/app/data" \
  puregym-bot
```

Or use Docker Compose:

```bash
mkdir -p data
docker compose up -d --build
```

This setup works well for local Raspberry Pi deployments where you build the image on the device and keep both config and database on the host.

## Test

```bash
uv run pytest
uv run python -m compileall puregym_bot tests
```

## Files

- `config.yaml`: bot runtime config
- `config_template.yaml`: template config to copy and edit
- `data/puregym_bot.db`: bot SQLite state
- `Dockerfile`: container image definition
- `compose.yml`: local deployment example with mounted config and data
- `puregym_bot/`: bot package
- `tests/`: bot test suite
