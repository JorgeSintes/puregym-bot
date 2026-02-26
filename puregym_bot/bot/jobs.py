import logging
from datetime import datetime, time, timedelta
from typing import cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from puregym_bot.config import config
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.puregym.filters import filter_by_booked, filter_by_time_slots
from puregym_bot.puregym.schemas import GymClass
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import BookingStatus, ManagedBooking
from puregym_bot.storage.repository import (
    add_managed_booking,
    get_active_bookings,
    get_active_users,
    get_booking_by_booking_id,
    get_booking_by_participation_id,
    get_pending_bookings,
    set_booking_status,
    set_message_id,
    set_reminder_sent,
)


def class_datetime(gym_class: GymClass) -> datetime:
    class_date = datetime.fromisoformat(gym_class.date).date()
    start_time = time.fromisoformat(gym_class.startTime)
    return datetime.combine(class_date, start_time)


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
    with get_db_session() as session:
        users = get_active_users(session)

    for user in users:
        clients = context.bot_data.get("puregym_clients", {})
        client = cast(PureGymClient, clients.get(user.telegram_id))
        if client is None:
            logging.info(f"No client for user {user.telegram_id}")
            continue

        logging.info(f"Running booking cycle for user {user.telegram_id}")

        classes = await client.get_available_classes(
            class_ids=config.class_preferences.interested_classes,
            center_ids=config.class_preferences.interested_centers,
        )
        classes = filter_by_time_slots(classes, config.class_preferences.available_time_slots)
        classes.sort(key=class_datetime)

        booked_classes = filter_by_booked(classes)
        booked_by_participation = {
            c.participationId: c for c in booked_classes if c.participationId is not None
        }

        with get_db_session() as session:
            active_bookings = get_active_bookings(session, user.id)
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
                        chat_id=user.telegram_id,
                        text="A booking has passed and is now archived.",
                    )
                else:
                    set_booking_status(session, booking, BookingStatus.CANCELLED)
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text="A booking was missing in PureGym and has been cancelled.",
                    )
                session.commit()

            # Handle bookings in PureGym that are not in DB (e.g. booked manually by user)
            for participation_id, gym_class in booked_by_participation.items():
                existing = get_booking_by_participation_id(session, participation_id)
                if existing is not None:
                    continue

                booking = ManagedBooking(
                    user_id=user.id,
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
                    chat_id=user.telegram_id,
                    text=message,
                    reply_markup=build_prompt_keyboard(participation_id),
                )
                set_message_id(session, booking, msg.message_id)
                session.commit()

            # Booking attempts (only those not already booked)
            for gym_class in classes:
                if gym_class.participationId is not None:
                    continue
                if get_booking_by_booking_id(session, gym_class.bookingId) is not None:
                    continue

                logging.info(f"Attempting to book class {gym_class.bookingId} for user {user.telegram_id}")
                resp = await client.book_class(gym_class)
                if resp.get("status") != "success":
                    logging.info(f"Booking failed for {gym_class.bookingId} user {user.telegram_id}: {resp}")
                    continue

                participation_id = resp.get("participationId")
                if not participation_id:
                    logging.info(
                        f"Booking response missing participationId for {gym_class.bookingId} user {user.telegram_id}: {resp}"
                    )
                    break

                booking = ManagedBooking(
                    user_id=user.id,
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
                    f"Booked: {gym_class.title} on {gym_class.date} at {gym_class.startTime} "
                    f"({gym_class.location}).\n"
                    "Do you want to keep it?"
                )
                msg = await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    reply_markup=build_prompt_keyboard(participation_id),
                )
                set_message_id(session, booking, msg.message_id)
                session.commit()

            # Reminders and auto-cancel
            pending = get_pending_bookings(session, user.id)
            for booking in pending:
                time_to_class = booking.class_datetime - now

                if time_to_class <= timedelta(hours=24) and not booking.reminder_sent:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            "Reminder: you have a pending booking in 24 hours.\nPlease accept or reject it."
                        ),
                    )
                    set_reminder_sent(session, booking)
                    session.commit()
                    logging.info(
                        f"Sent 24h reminder for booking {booking.booking_id} user {user.telegram_id}"
                    )

                if time_to_class <= timedelta(hours=3):
                    if booking.participation_id is None:
                        continue
                    resp = await client.unbook_participation(booking.participation_id)
                    if resp.get("status") == "success":
                        set_booking_status(session, booking, BookingStatus.CANCELLED)
                        session.commit()
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            text="Pending booking was cancelled 3h before class time.",
                        )
                        logging.info(f"Auto-cancelled booking {booking.booking_id} user {user.telegram_id}")
                    else:
                        logging.info(
                            f"Failed to auto-cancel booking {booking.booking_id} user {user.telegram_id}: {resp}"
                        )
