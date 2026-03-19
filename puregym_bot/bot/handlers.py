import json
import logging
from datetime import datetime, time

from telegram import Update
from telegram.ext import ContextTypes

from puregym_bot.bot.booking_cycle import build_prompt_keyboard, run_booking_cycle
from puregym_bot.bot.dependencies import HandlerContext
from puregym_bot.config import config
from puregym_bot.puregym.filters import filter_by_booked
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import BookingStatus, ChoiceStatus, ManagedBooking
from puregym_bot.storage.repository import (
    get_booking_by_participation_id,
    get_choice_by_id,
    set_booking_status,
    set_bot_active,
    set_choice_status,
)


def option_datetime(option: dict) -> datetime:
    class_date = datetime.fromisoformat(option["date"]).date()
    start_time = time.fromisoformat(option["startTime"])
    return datetime.combine(class_date, start_time)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None or update.effective_user is None:
        return
    set_bot_active(ctx.session, True)
    ctx.session.commit()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"Hey {config.name}! Automatic booking is now enabled. "
            "I will keep running the booking cycle for you."
        ),
    )


async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    set_bot_active(ctx.session, False)
    ctx.session.commit()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"Hey {config.name}! Automatic booking is now disabled. "
            "You can still use the other commands whenever you want."
        ),
    )


async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    auto_booking_status = "enabled" if ctx.bot_active else "disabled"
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"Automatic booking is currently {auto_booking_status}. "
            "Use /start to enable it or /stop to disable it."
        ),
    )


async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or update.effective_user is None:
        return
    if update.effective_user.id != config.telegram_id:
        return

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    data = query.data or ""
    if data.startswith("accept:") or data.startswith("reject:") or data.startswith("cancel:"):
        action, participation_id = data.split(":", 1)
        with get_db_session() as session:
            booking = get_booking_by_participation_id(session, participation_id)
            if booking is None:
                return

            if action in {"accept", "reject"} and booking.status != BookingStatus.PENDING:
                await query.edit_message_text(text="This booking has already been handled.")
                return

            if action == "cancel" and booking.status not in {
                BookingStatus.PENDING,
                BookingStatus.CONFIRMED,
            }:
                await query.edit_message_text(text="This booking can no longer be cancelled.")
                return

            if action == "accept":
                set_booking_status(session, booking, BookingStatus.CONFIRMED)
                session.commit()
                await query.edit_message_text(text="Booking accepted.")
                return

            client = context.bot_data.get("puregym_client")
            if client is None:
                return
            resp = await client.unbook_participation(participation_id)
            if resp.get("status") == "success":
                set_booking_status(session, booking, BookingStatus.CANCELLED)
                session.commit()
                await query.edit_message_text(text="Booking cancelled.")
            else:
                logging.debug("Failed to cancel booking %s: %s", participation_id, resp)
                await query.edit_message_text(text="Failed to cancel. I will retry later.")
        return

    if data.startswith("pick:"):
        _, choice_id_str, idx_str = data.split(":", 2)
        with get_db_session() as session:
            choice = get_choice_by_id(session, int(choice_id_str))
            if choice is None:
                return
            if choice.status != ChoiceStatus.PENDING:
                await query.edit_message_text(text="This selection has already been handled.")
                return

            options = json.loads(choice.options_json)
            idx = int(idx_str)
            if idx < 0 or idx >= len(options):
                return
            selected = options[idx]

            client = context.bot_data.get("puregym_client")
            if client is None:
                return

            resp = await client.book_by_ids(
                selected["booking_id"],
                selected["activity_id"],
                selected["payment_type"],
            )
            if resp.get("status") != "success":
                logging.debug("Failed to book selected option: %s", resp)
                await query.edit_message_text(text="Failed to book that option. Please choose another.")
                return

            participation_id = resp.get("participationId")
            if not participation_id:
                await query.edit_message_text(
                    text="Booking succeeded but response was incomplete. Please try again."
                )
                return

            booking = ManagedBooking(
                booking_id=selected["booking_id"],
                activity_id=selected["activity_id"],
                payment_type=selected["payment_type"],
                participation_id=participation_id,
                class_datetime=option_datetime(selected),
                status=BookingStatus.PENDING,
            )
            session.add(booking)
            set_choice_status(session, choice, ChoiceStatus.HANDLED)
            session.commit()

            await query.edit_message_text(text="Booked your selection. Please accept or reject.")
            await context.bot.send_message(
                chat_id=config.telegram_id,
                text=(
                    f"Booked: {selected['title']} on {selected['date']} at {selected['startTime']} "
                    f"({selected['location']})\nDo you want to keep it?"
                ),
                reply_markup=build_prompt_keyboard(participation_id),
            )
        return

    await query.edit_message_text(text=f"Selected option: {query.data}")


async def booked_classes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    bookings = await ctx.client.get_available_classes(
        class_ids=config.class_preferences.interested_classes,
        center_ids=config.class_preferences.interested_centers,
    )
    bookings = filter_by_booked(bookings)
    if not bookings:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="You have no upcoming bookings."
        )
        return

    message = "Your upcoming bookings:\n"
    for booking in bookings:
        message += f"- {booking.format()}\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def all_class_ids(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    class_groups = await ctx.client.get_all_class_types()
    lines = ["🏋 <b>Available Class Types</b>\n"]
    for group in class_groups:
        lines.append(group.format())
        lines.append("")  # blank line between groups

    message = "\n".join(lines)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode="HTML")


async def all_center_ids(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    center_groups = await ctx.client.get_all_centers()
    lines = ["🏢 <b>Available Centers</b>\n"]
    for group in center_groups:
        lines.append(group.format())
        lines.append("")  # blank line between groups

    message = "\n".join(lines)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode="HTML")


async def run_now(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return
    if context.job_queue is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Job queue is not available.",
        )
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Running booking cycle now...",
    )
    context.job_queue.run_once(callback=run_booking_cycle, when=0)
