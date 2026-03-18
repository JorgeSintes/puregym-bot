import json
import logging
from datetime import datetime, time, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from puregym_bot.config import TimeSlot, config
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.puregym.filters import filter_by_booked, filter_by_time_slots
from puregym_bot.puregym.schemas import GymClass
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import BookingChoice, BookingStatus, ManagedBooking
from puregym_bot.storage.repository import (
    add_booking_choice,
    add_managed_booking,
    get_bot_state,
    get_active_bookings,
    get_booking_by_participation_id,
    get_pending_bookings,
    get_pending_choice,
    set_booking_status,
    set_choice_message_id,
    set_message_id,
    set_reminder_sent,
)


def class_datetime(gym_class: GymClass) -> datetime:
    class_date = datetime.fromisoformat(gym_class.date).date()
    start_time = time.fromisoformat(gym_class.startTime)
    return datetime.combine(class_date, start_time)


def slot_key(gym_class: GymClass, time_slots: list[TimeSlot]) -> tuple[str, str, str] | None:
    class_date = datetime.fromisoformat(gym_class.date).date()
    weekday = class_date.weekday()
    class_start = time.fromisoformat(gym_class.startTime)
    class_end = time.fromisoformat(gym_class.endTime)

    for slot in time_slots:
        if slot.day_of_week != weekday:
            continue
        if slot.start_time <= class_start <= class_end <= slot.end_time:
            return (gym_class.date, slot.start_time.isoformat(), slot.end_time.isoformat())
    return None


def group_by_slot(
    classes: list[GymClass], time_slots: list[TimeSlot]
) -> dict[tuple[str, str, str], list[GymClass]]:
    grouped: dict[tuple[str, str, str], list[GymClass]] = {}
    for c in classes:
        key = slot_key(c, time_slots)
        if key is None:
            continue
        grouped.setdefault(key, []).append(c)
    return grouped


def build_prompt_keyboard(participation_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Accept", callback_data=f"accept:{participation_id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{participation_id}"),
            ]
        ]
    )


async def run_booking_cycle(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now()
    client = context.bot_data.get("puregym_client")
    if not isinstance(client, PureGymClient):
        raise ValueError("No PureGym client found")

    with get_db_session() as session:
        bot_state = get_bot_state(session)
        if bot_state.is_active is False:
            logging.info("Booking cycle skipped because bot is inactive")
            return

    logging.info("Running booking cycle")

    classes = await client.get_available_classes(
        class_ids=config.class_preferences.interested_classes,
        center_ids=config.class_preferences.interested_centers,
    )
    classes = filter_by_time_slots(classes, config.class_preferences.available_time_slots)
    classes.sort(key=class_datetime)

    booked_classes = filter_by_booked(classes)
    booked_by_participation = {c.participationId: c for c in booked_classes if c.participationId is not None}

    with get_db_session() as session:
        active_bookings = get_active_bookings(session)
        # Handle bookings in DB that are not in PureGym anymore (either attended, expired or cancelled)
        for booking in active_bookings:
            if booking.participation_id in booked_by_participation:
                continue

            if booking.class_datetime <= now:
                if booking.status == BookingStatus.CONFIRMED:
                    set_booking_status(session, booking, BookingStatus.ATTENDED)
                else:
                    set_booking_status(session, booking, BookingStatus.EXPIRED)
                await context.bot.send_message(
                    chat_id=config.telegram_id,
                    text="A booking has passed and is now archived.",
                )
            else:
                set_booking_status(session, booking, BookingStatus.CANCELLED)
                await context.bot.send_message(
                    chat_id=config.telegram_id,
                    text="A booking was missing in PureGym and has been cancelled.",
                )
            session.commit()

        # Handle bookings in PureGym that are not in DB (e.g. booked manually by user)
        for participation_id, gym_class in booked_by_participation.items():
            existing = get_booking_by_participation_id(session, participation_id)
            if existing is not None:
                continue

            booking = ManagedBooking(
                booking_id=gym_class.bookingId,
                activity_id=gym_class.activityId,
                payment_type=gym_class.payment_type,
                participation_id=participation_id,
                class_datetime=class_datetime(gym_class),
                status=BookingStatus.PENDING,
            )
            add_managed_booking(session, booking)
            session.commit()

            message = (
                f"Found a booking not tracked by the bot:\n"
                f"- {gym_class.title} on {gym_class.date} at {gym_class.startTime} "
                f"({gym_class.location})\n"
                "Do you want to keep it?"
            )
            msg = await context.bot.send_message(
                chat_id=config.telegram_id,
                text=message,
                reply_markup=build_prompt_keyboard(participation_id),
            )
            set_message_id(session, booking, msg.message_id)
            session.commit()

        # Booking attempts and slot choice prompts
        grouped = group_by_slot(classes, config.class_preferences.available_time_slots)
        active_count = len(booked_by_participation)

        for (slot_date, slot_start, slot_end), slot_classes in grouped.items():
            if active_count >= config.max_bookings:
                logging.info("Max bookings reached, skipping further booking attempts")
                break

            pending_choice = get_pending_choice(session, slot_date, slot_start, slot_end)
            if pending_choice is not None:
                continue

            available = [c for c in slot_classes if c.participationId is None]
            if not available:
                continue

            if len(available) == 1:
                gym_class = available[0]
                logging.info("Attempting to book class %s", gym_class.bookingId)
                resp = await client.book_class(gym_class)
                if resp.get("status") != "success":
                    logging.info("Booking failed for %s: %s", gym_class.bookingId, resp)
                    continue

                participation_id = resp.get("participationId")
                if not participation_id:
                    logging.info(
                        "Booking response missing participationId for %s: %s",
                        gym_class.bookingId,
                        resp,
                    )
                    continue

                booking = ManagedBooking(
                    booking_id=gym_class.bookingId,
                    activity_id=gym_class.activityId,
                    payment_type=gym_class.payment_type,
                    participation_id=participation_id,
                    class_datetime=class_datetime(gym_class),
                    status=BookingStatus.PENDING,
                )
                add_managed_booking(session, booking)
                session.commit()
                active_count += 1

                message = f"Booked: {gym_class.format()}\nDo you want to keep it?"
                msg = await context.bot.send_message(
                    chat_id=config.telegram_id,
                    text=message,
                    reply_markup=build_prompt_keyboard(participation_id),
                )
                set_message_id(session, booking, msg.message_id)
                session.commit()
                continue

            options = []
            for c in sorted(available, key=class_datetime):
                options.append(
                    {
                        "booking_id": c.bookingId,
                        "activity_id": c.activityId,
                        "payment_type": c.payment_type,
                        "title": c.title,
                        "date": c.date,
                        "startTime": c.startTime,
                        "location": c.location,
                    }
                )

            choice = BookingChoice(
                slot_date=slot_date,
                slot_start=slot_start,
                slot_end=slot_end,
                options_json=json.dumps(options),
            )
            add_booking_choice(session, choice)
            session.commit()

            lines = ["Multiple classes match this time slot. Pick one to book:"]
            for idx, opt in enumerate(options, start=1):
                lines.append(
                    f"{idx}. {opt['title']} on {opt['date']} at {opt['startTime']} ({opt['location']})"
                )
            message = "\n".join(lines)

            keyboard = []
            for idx, opt in enumerate(options):
                label = f"{idx + 1}. {opt['startTime']} {opt['title']}"
                keyboard.append([InlineKeyboardButton(label, callback_data=f"pick:{choice.id}:{idx}")])

            msg = await context.bot.send_message(
                chat_id=config.telegram_id,
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            set_choice_message_id(session, choice, msg.message_id)
            session.commit()

        # Reminders and auto-cancel
        pending = get_pending_bookings(session)
        for booking in pending:
            time_to_class = booking.class_datetime - now

            if time_to_class <= timedelta(hours=24) and not booking.reminder_sent:
                await context.bot.send_message(
                    chat_id=config.telegram_id,
                    text="Reminder: you have a pending booking in 24 hours.\nPlease accept or reject it.",
                )
                set_reminder_sent(session, booking)
                session.commit()
                logging.info("Sent 24h reminder for booking %s", booking.booking_id)

            if time_to_class <= timedelta(hours=3):
                if booking.participation_id is None:
                    continue
                resp = await client.unbook_participation(booking.participation_id)
                if resp.get("status") == "success":
                    set_booking_status(session, booking, BookingStatus.CANCELLED)
                    session.commit()
                    await context.bot.send_message(
                        chat_id=config.telegram_id,
                        text="Pending booking was cancelled 3h before class time.",
                    )
                    logging.info("Auto-cancelled booking %s", booking.booking_id)
                else:
                    logging.info("Failed to auto-cancel booking %s: %s", booking.booking_id, resp)
