from telegram import Update
from telegram.ext import ContextTypes

from puregym_bot.bot.dependencies import require_client
from puregym_bot.puregym.client import PureGymClient


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello! I'm your PureGym booking bot. Use /booked_classes to see your upcoming bookings.",
    )


@require_client
async def booked_classes(
    update: Update, context: ContextTypes.DEFAULT_TYPE, client: PureGymClient
):
    if update.effective_chat is None:
        return

    bookings = await client.get_booked_classes()
    if not bookings:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="You have no upcoming bookings."
        )
        return

    message = "Your upcoming bookings:\n"
    for booking in bookings:
        message += f"- {booking.title}, {booking.date} at {booking.startTime} at {booking.location}\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@require_client
async def all_class_ids(
    update: Update, context: ContextTypes.DEFAULT_TYPE, client: PureGymClient
):
    if update.effective_chat is None:
        return

    class_groups = await client.get_all_class_types()
    lines = ["🏋 <b>Available Class Types</b>\n"]
    for group in class_groups:
        lines.append(group.format())
        lines.append("")  # blank line between groups

    message = "\n".join(lines)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=message, parse_mode="HTML"
    )


@require_client
async def all_center_ids(
    update: Update, context: ContextTypes.DEFAULT_TYPE, client: PureGymClient
):
    if update.effective_chat is None:
        return

    center_groups = await client.get_all_centers()
    lines = ["🏢 <b>Available Centers</b>\n"]
    for group in center_groups:
        lines.append(group.format())
        lines.append("")  # blank line between groups

    message = "\n".join(lines)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=message, parse_mode="HTML"
    )
