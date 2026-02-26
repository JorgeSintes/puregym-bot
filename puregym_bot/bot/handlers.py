from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from puregym_bot.bot.dependencies import require_client
from puregym_bot.config import config
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.puregym.filters import filter_by_booked
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import User
from puregym_bot.storage.repository import set_user_active


@require_client
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: PureGymClient,
    user: User,
):
    if update.effective_chat is None:
        return

    with get_db_session() as session:
        set_user_active(session, user, True)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hey {user.name}! I'm your PureGym booking bot. I will start making bookings for you.",
    )


@require_client
async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: PureGymClient,
    user: User,
):
    if update.effective_chat is None:
        return

    with get_db_session() as session:
        set_user_active(session, user, False)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hey {user.name}! I will stop making bookings for you. See you next time!",
    )


async def test_inline(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    await query.edit_message_text(text=f"Selected option: {query.data}")


@require_client
async def booked_classes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: PureGymClient,
    user: User,
):
    if update.effective_chat is None:
        return

    bookings = await client.get_available_classes(
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


@require_client
async def all_class_ids(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: PureGymClient,
    user: User,
):
    if update.effective_chat is None:
        return

    class_groups = await client.get_all_class_types()
    lines = ["🏋 <b>Available Class Types</b>\n"]
    for group in class_groups:
        lines.append(group.format())
        lines.append("")  # blank line between groups

    message = "\n".join(lines)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode="HTML")


@require_client
async def all_center_ids(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: PureGymClient,
    user: User,
):
    if update.effective_chat is None:
        return

    center_groups = await client.get_all_centers()
    lines = ["🏢 <b>Available Centers</b>\n"]
    for group in center_groups:
        lines.append(group.format())
        lines.append("")  # blank line between groups

    message = "\n".join(lines)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode="HTML")
