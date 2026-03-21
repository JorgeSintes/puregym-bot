# AGENTS

## Repo Overview

- This repo contains only the single-user Telegram bot.
- The bot depends on the separate `puregym-mcp` repo as a package dependency.
- By default, `pyproject.toml` resolves `puregym-mcp` from GitHub.
- Local sibling checkouts of `puregym-mcp` are optional and may be used as temporary development overrides.
- The bot remains single-user.
- The configured owner is the only Telegram user allowed to interact with the bot.
- The bot polls PureGym for matching classes, tracks booking state locally, and asks the user to confirm or reject bookings through Telegram.

## Main Architecture

- `puregym_bot/config.py`
  - Loads bot config eagerly from `config.yaml` at the repo root.
  - Holds single-user Telegram/PureGym credentials and booking thresholds.
- `puregym_bot/bot/app.py`
  - Builds the Telegram app and schedules the booking cycle job.
- `puregym_bot/bot/dependencies.py`
  - Wires the single shared `PureGymClient` from `puregym_mcp` and authorizes only `config.telegram_id`.
- `puregym_bot/bot/handlers.py`
  - Telegram commands and callback handlers.
  - `/start` and `/stop` toggle automatic booking via the global bot activity state.
  - Informational commands still work while automatic booking is stopped.
  - Callback flows currently support `accept:`, `reject:`, `pick:`, and `cancel:`.
- `puregym_bot/bot/booking_cycle.py`
  - Contains the booking-cycle orchestration and step logic.
  - Uses dataclass-based prompt outputs to keep the flow testable.
- `puregym_bot/storage/models.py`
  - `BotState`: singleton global on/off state.
  - `ManagedBooking`: tracked bookings and reminder state.
  - `BookingChoice`: pending multi-option slot selections.
- `puregym_bot/storage/repository.py`
  - DB access helpers for bot state, bookings, and booking choices.

## Important Domain Rules

- The app is single-user. Do not reintroduce per-user DB models or `config.users` unless explicitly requested.
- The bot imports PureGym client/domain code from `puregym_mcp`; do not re-copy that logic into this repo.
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
  - `uv sync --dev`
  - `uv run pytest`
  - `uv run python -m compileall puregym_bot tests`
  - `uv add ...` / `uv sync` when dependency changes are needed
- Do not use plain `python`, `pip`, or ad-hoc environment commands when `uv` can do the job.

## Testing Expectations

- After implementing any non-trivial change, always run the tests.
- If tests fail, do not stop with the repo in a failing state unless the user explicitly asks for that.
- Keep working until the tests pass again.
- If behavior changes, update or add tests to reflect the intended behavior.
- Tests live in `tests/` for bot, booking-cycle, and storage coverage.

## Practical Notes

- Be careful with config imports: `config` is instantiated at import time.
- Keep Telegram presentation helpers in `puregym_bot` concerns and structured domain data in `puregym_mcp` concerns.
- Preserve the single-user assumptions across config, handlers, jobs, and DB models.
- If changing callback behavior, also review the prompt builders in `puregym_bot/bot/booking_cycle.py` and the callback handling in `puregym_bot/bot/handlers.py` together.
- If changing booking-cycle timing behavior, also update `config_template.yaml` and tests.

## Good Validation Commands

- `uv sync --dev`
- `uv run pytest`
- `uv run python -m compileall puregym_bot tests`
- `uv run puregym-bot`
