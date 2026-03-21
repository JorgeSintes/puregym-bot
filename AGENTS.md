# AGENTS

## Repo Overview

- This repo is now a two-project workspace:
  - `puregym_mcp/`: the publishable PureGym client library and MCP server package.
  - `puregym_bot/`: the single-user Telegram bot built on top of `puregym-mcp`.
- The bot remains single-user.
- The configured owner is the only Telegram user allowed to interact with the bot.
- The bot polls PureGym for matching classes, tracks booking state locally, and asks the user to confirm or reject bookings through Telegram.
- The MCP package exposes structured PureGym data plus derived fields like waitlist status.

## Main Architecture

- `puregym_mcp/puregym_mcp/puregym/client.py`
  - Low-level PureGym HTTP client and login/session handling.
  - Supports anonymous mode when credentials are absent and authenticated mode when env credentials are present.
- `puregym_mcp/puregym_mcp/puregym/service.py`
  - Reusable service layer used by both MCP tools and the bot.
  - Owns default search windows: 14 days anonymous, 28 days authenticated.
- `puregym_mcp/puregym_mcp/puregym/schemas.py`
  - Structured PureGym models.
  - Includes derived fields like `is_booked`, `is_waitlisted`, `waitlist_position`, and `waitlist_size`.
- `puregym_mcp/puregym_mcp/mcp/server.py`
  - MCP server bootstrap.
- `puregym_mcp/puregym_mcp/mcp/tools.py`
  - MCP tool registration.
  - Always exposes read-only tools; exposes mutation tools only in authenticated mode.
- `puregym_bot/puregym_bot/config.py`
  - Loads bot config eagerly from `puregym_bot/config.yaml`.
  - Holds single-user Telegram/PureGym credentials and booking thresholds.
- `puregym_bot/puregym_bot/bot/app.py`
  - Builds the Telegram app and schedules the booking cycle job.
- `puregym_bot/puregym_bot/bot/dependencies.py`
  - Wires the single shared `PureGymClient` from `puregym_mcp` and authorizes only `config.telegram_id`.
- `puregym_bot/puregym_bot/bot/handlers.py`
  - Telegram commands and callback handlers.
  - `/start` and `/stop` toggle automatic booking via the global bot activity state.
  - Informational commands still work while automatic booking is stopped.
  - Callback flows currently support `accept:`, `reject:`, `pick:`, and `cancel:`.
- `puregym_bot/puregym_bot/bot/booking_cycle.py`
  - Contains the booking-cycle orchestration and step logic.
  - Uses dataclass-based prompt outputs to keep the flow testable.
- `puregym_bot/puregym_bot/storage/models.py`
  - `BotState`: singleton global on/off state.
  - `ManagedBooking`: tracked bookings and reminder state.
  - `BookingChoice`: pending multi-option slot selections.
- `puregym_bot/puregym_bot/storage/repository.py`
  - DB access helpers for bot state, bookings, and booking choices.

## Important Domain Rules

- The app is single-user. Do not reintroduce per-user DB models or `config.users` unless explicitly requested.
- `puregym_mcp` has two intended modes:
  - Anonymous/read-only mode for hosted/public use.
  - Authenticated mode for self-hosted use via `PUREGYM_USERNAME` and `PUREGYM_PASSWORD` env vars.
- Do not design for hosted authenticated MCP. That is intentionally out of scope.
- MCP tool outputs should stay structured and derived, not Telegram-formatted.
- `/start` enables automatic booking and `/stop` disables it via `BotState.is_active`.
- Informational/manual commands may still run while `BotState.is_active` is false.
- `ManagedBooking.reminder_sent` is a single reminder flag:
  - If a pending booking is reminded, do not remind again after it is accepted.
  - If a confirmed booking is reminded, do not remind again.
- Pending reminders use accept/reject buttons.
- Confirmed reminders use a last-minute `cancel:` button.
- Pending bookings may be auto-cancelled when close to class time.

## Workflow Rules For Future Changes

- Always use `uv` for project commands.
- Prefer:
  - `uv sync --all-packages --all-groups`
  - `uv run --package puregym-mcp pytest`
  - `uv run --package puregym-bot pytest`
  - `uv run --package puregym-mcp python -m compileall puregym_mcp tests`
  - `uv run --package puregym-bot python -m compileall puregym_bot tests`
  - `uv add ...` / `uv sync` when dependency changes are needed
- Do not use plain `python`, `pip`, or ad-hoc environment commands when `uv` can do the job.

## Testing Expectations

- After implementing any non-trivial change, always run the tests.
- If tests fail, do not stop with the repo in a failing state unless the user explicitly asks for that.
- Keep working until the tests pass again.
- If behavior changes, update or add tests to reflect the intended behavior.
- Tests now live per project:
  - `puregym_mcp/tests/` for client/service/schema/MCP coverage.
  - `puregym_bot/tests/` for bot, booking-cycle, and storage coverage.

## Practical Notes

- Be careful with config imports: `config` is instantiated at import time.
- `puregym_bot` should import PureGym client/domain code from `puregym_mcp`, not from its own package.
- Keep Telegram presentation helpers in `puregym_bot` concerns and structured domain data in `puregym_mcp` concerns.
- For MCP work, keep tool handlers thin and put business logic in `puregym_mcp/puregym_mcp/puregym/service.py`.
- Preserve the single-user assumptions across config, handlers, jobs, and DB models.
- If changing callback behavior, also review the prompt builders in `puregym_bot/bot/booking_cycle.py` and the callback handling in `puregym_bot/bot/handlers.py` together.
- If changing booking-cycle timing behavior, also update bot config defaults, `puregym_bot/config_template.yaml`, and tests.

## Good Validation Commands

- `uv sync --all-packages --all-groups`
- `uv run --package puregym-mcp pytest`
- `uv run --package puregym-bot pytest`
- `uv run --package puregym-mcp python -m compileall puregym_mcp tests`
- `uv run --package puregym-bot python -m compileall puregym_bot tests`
- `uv run --package puregym-mcp puregym-mcp`
- `uv run --package puregym-bot puregym-bot`
