# PureGym Bot

Single-user Telegram bot for automatically booking PureGym classes that match a configured schedule.

## What it does

- Runs the booking cycle automatically while auto-booking is enabled
- Sends Telegram prompts so you can accept or reject pending bookings
- Sends reminders before class time
- Cancels stale pending bookings before they get too close to class time
- Keeps track of booking state locally so it does not repeatedly prompt for the same slot

## Commands

- `/start` enables automatic booking-cycle runs
- `/stop` disables automatic booking-cycle runs
- `/status` shows whether automatic booking is currently enabled
- `/booked` shows your upcoming booked classes
- `/manage_bookings` shows upcoming bookings you can accept, reject, or cancel
- `/class_ids` lists available class types so you can update the config
- `/center_ids` lists available centers so you can update the config
- `/run_now` queues an immediate booking-cycle run

When automatic booking is disabled, the informational commands still work. `/run_now` also still works as a command, but the booking cycle will respect the disabled state and skip booking.

## Notes

- The bot is configured for one Telegram user and one PureGym account
- Class matching is based on configured class IDs, center IDs, and weekly time slots
- The booking window currently looks ahead up to 28 days
