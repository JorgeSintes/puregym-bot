# PureGym Workspace

This repository contains two related projects:

- `puregym_mcp/`: a publishable PureGym client library and MCP server
- `puregym_bot/`: a private single-user Telegram bot built on top of `puregym-mcp`

## What Each Project Does

### `puregym_mcp`

- Exposes structured PureGym data for LLM tooling through MCP
- Supports anonymous read-only mode for public/hosted use
- Supports authenticated self-hosted mode through `PUREGYM_USERNAME` and `PUREGYM_PASSWORD`
- Returns structured fields plus derived values like `is_booked`, `is_waitlisted`, `waitlist_position`, and `waitlist_size`

Current MCP tool set:

- always available:
  - `get_capabilities`
  - `list_class_types`
  - `list_centers`
  - `search_classes`
- authenticated only:
  - `list_my_bookings`
  - `book_class`
  - `cancel_booking`

### `puregym_bot`

- Polls PureGym for matching classes based on configured preferences and time slots
- Prebooks matching classes for one Telegram user
- Tracks managed booking state locally in SQLite
- Asks the user to accept, reject, or cancel bookings through Telegram
- Shows waitlist state and unmanaged bookings alongside bot-managed ones

## Repository Structure

```text
repo/
  puregym_mcp/
    pyproject.toml
    puregym_mcp/
    tests/
  puregym_bot/
    pyproject.toml
    puregym_bot/
    config.yaml
    config_template.yaml
    tests/
```

## Install

From the workspace root:

```bash
uv sync --all-packages --all-groups
```

## Common Commands

Run the MCP server:

```bash
uv run --package puregym-mcp puregym-mcp
```

Run the Telegram bot:

```bash
uv run --package puregym-bot puregym-bot
```

Run tests:

```bash
uv run --package puregym-mcp pytest
uv run --package puregym-bot pytest
```

## Notes

- Hosted authenticated MCP is intentionally out of scope
- Self-hosted authenticated MCP uses local env vars, not credential-passing through tool calls
- The Telegram bot is single-user by design
- The bot imports PureGym client/domain code from `puregym_mcp`

See `puregym_mcp/README.md` for MCP usage/config examples and `puregym_bot/README.md` for bot setup details.
