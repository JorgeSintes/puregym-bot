from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from puregym_bot.bot.dependencies import HandlerContext
from puregym_bot.config import config
from puregym_bot.puregym.filters import filter_by_booked
from puregym_bot.storage.repository import set_user_active


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None or update.effective_user is None:
        return
    set_user_active(ctx.session, ctx.user, True)

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
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

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
