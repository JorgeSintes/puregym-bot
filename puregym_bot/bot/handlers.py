import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from puregym_bot.bot.dependencies import HandlerContext
from puregym_bot.config import config
from puregym_bot.puregym.filters import filter_by_booked
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import BookingStatus
from puregym_bot.bot.jobs import run_booking_cycle
from puregym_bot.storage.repository import (
    get_booking_by_participation_id,
    get_user_by_telegram_id,
    set_booking_status,
    set_user_active,
)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None or update.effective_user is None:
        return
    set_user_active(ctx.session, ctx.user, True)
    ctx.session.commit()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hey {ctx.user.name}! I'm your PureGym booking bot. I will start making bookings for you.",
    )


async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    set_user_active(ctx.session, ctx.user, False)
    ctx.session.commit()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hey {ctx.user.name}! I will stop making bookings for you. See you next time!",
    )


async def test_inline(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None or update.message is None:
        return

    await update.message.reply_text(
        "Choose an option:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Option 1", callback_data="option_1"),
                    InlineKeyboardButton("Option 2", callback_data="option_2"),
                ]
            ]
        ),
    )


async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or update.effective_user is None:
        return

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    data = query.data or ""
    if data.startswith("accept:") or data.startswith("reject:"):
        action, participation_id = data.split(":", 1)
        with get_db_session() as session:
            user = get_user_by_telegram_id(session, update.effective_user.id)
            if user is None:
                return
            booking = get_booking_by_participation_id(session, participation_id)
            if booking is None or booking.user_id != user.id:
                return

            if booking.status != BookingStatus.PENDING:
                await query.edit_message_text(text="This booking has already been handled.")
                return

            if action == "accept":
                set_booking_status(session, booking, BookingStatus.CONFIRMED)
                session.commit()
                await query.edit_message_text(text="Booking accepted.")
                return

            clients = context.bot_data.get("puregym_clients", {})
            client = clients.get(user.telegram_id)
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
        message += f"- {booking.title}, {booking.date} at {booking.startTime} at {booking.location}\n"
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
    await context.job_queue.run_once(callback=run_booking_cycle, when=0)
