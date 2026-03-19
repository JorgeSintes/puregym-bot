# AGENTS

## Repo Overview

- This is a single-user PureGym Telegram bot.
- The configured owner is the only Telegram user allowed to interact with the bot.
- The bot polls PureGym for matching classes, tracks booking state locally, and asks the user to confirm or reject bookings through Telegram.

## Main Architecture

- `puregym_bot/config.py`
  - Loads config eagerly via the module-level `config` object.
  - Holds the single-user Telegram/PureGym credentials and booking thresholds.
- `puregym_bot/bot/app.py`
  - Builds the Telegram app and schedules the booking cycle job.
- `puregym_bot/bot/dependencies.py`
  - Wires the single shared `PureGymClient` and authorizes only `config.telegram_id`.
- `puregym_bot/bot/handlers.py`
  - Telegram commands and callback handlers.
  - `/start` and `/stop` toggle the global bot activity state.
  - Callback flows currently support `accept:`, `reject:`, `pick:`, and `cancel:`.
- `puregym_bot/bot/jobs.py`
  - Contains the booking-cycle orchestration and step logic.
  - Uses dataclass-based prompt outputs to keep the flow testable.
- `puregym_bot/storage/models.py`
  - `BotState`: singleton global on/off state.
  - `ManagedBooking`: tracked bookings and reminder state.
  - `BookingChoice`: pending multi-option slot selections.
- `puregym_bot/storage/repository.py`
  - DB access helpers for bot state, bookings, and booking choices.
- `puregym_bot/puregym/client.py`
  - PureGym HTTP client.
  - Keep date defaults runtime-computed, not import-time computed.

## Important Domain Rules

- The app is single-user. Do not reintroduce per-user DB models or `config.users` unless explicitly requested.
- `/start` and `/stop` control one global bot state via `BotState.is_active`.
- `ManagedBooking.reminder_sent` is a single reminder flag:
  - If a pending booking is reminded, do not remind again after it is accepted.
  - If a confirmed booking is reminded, do not remind again.
- Pending reminders use accept/reject buttons.
- Confirmed reminders use a last-minute `cancel:` button.
- Pending bookings may be auto-cancelled when close to class time.

## Workflow Rules For Future Changes

- Always use `uv` for project commands.
- Prefer:
  - `uv run pytest`
  - `uv run python -m compileall puregym_bot tests`
  - `uv add ...` / `uv sync` when dependency changes are needed
- Do not use plain `python`, `pip`, or ad-hoc environment commands when `uv` can do the job.

## Testing Expectations

- After implementing any non-trivial change, always run the tests.
- If tests fail, do not stop with the repo in a failing state unless the user explicitly asks for that.
- Keep working until the tests pass again.
- If behavior changes, update or add tests to reflect the intended behavior.
- Existing tests live under `tests/` and include both unit and integration coverage for the booking cycle.

## Practical Notes

- Be careful with config imports: `config` is instantiated at import time.
- Preserve the single-user assumptions across config, handlers, jobs, and DB models.
- If changing callback behavior, also review the prompt builders in `puregym_bot/bot/jobs.py` and the callback handling in `puregym_bot/bot/handlers.py` together.
- If changing booking-cycle timing behavior, also update config defaults, template config, and tests.

## Good Validation Commands

- `uv run pytest`
- `uv run python -m compileall puregym_bot tests`
- `uv run python -m puregym_bot.main`
