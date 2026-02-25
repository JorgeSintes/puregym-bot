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
