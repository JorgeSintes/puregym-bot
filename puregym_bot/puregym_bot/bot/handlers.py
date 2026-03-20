import json
import logging
from dataclasses import dataclass
from datetime import datetime, time

from telegram import Update
from telegram.ext import ContextTypes

from puregym_bot.bot.booking_cycle import run_booking_cycle
from puregym_bot.bot.callback_data import (
    BookingCallback,
    BookingCallbackAction,
    ChoicePickCallback,
    parse_callback_data,
)
from puregym_bot.bot.dependencies import HandlerContext
from puregym_bot.bot.prompts import (
    build_cancel_booking_prompt,
    build_keep_booking_prompt,
    build_selected_choice_confirmation_prompt,
    message_markup,
)
from puregym_bot.config import get_config
from puregym_bot.formatting import format_telegram_class_time, format_telegram_gym_class
from puregym_mcp.puregym.client import PureGymClient
from puregym_mcp.puregym.filters import filter_by_booked
from puregym_mcp.puregym.schemas import GymClass
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import BookingStatus, ChoiceStatus, ManagedBooking
from puregym_bot.storage.repository import (
    get_active_bookings,
    get_booking_by_participation_id,
    get_choice_by_id,
    set_booking_status,
    set_bot_active,
    set_choice_status,
)


@dataclass(frozen=True)
class ActionableBooking:
    gym_class: GymClass
    managed_booking: ManagedBooking | None


def option_datetime(option: dict) -> datetime:
    class_date = datetime.fromisoformat(option["date"]).date()
    start_time = time.fromisoformat(option["startTime"])
    return datetime.combine(class_date, start_time)


def managed_booking_label(status: BookingStatus) -> str:
    if status == BookingStatus.CONFIRMED:
        return "confirmed"
    return status.value


def booking_state_label(managed_booking: ManagedBooking | None) -> str:
    if managed_booking is None:
        return "external"
    return managed_booking_label(managed_booking.status)


def format_booking_line(gym_class: GymClass, state: str) -> str:
    line = (
        f"- {format_telegram_class_time(gym_class.date, gym_class.startTime)}  "
        f"{gym_class.title} @ {gym_class.location} - {state}"
    )
    if gym_class.waitlist_position is not None:
        return f"{line}, waitlist #{gym_class.waitlist_position}"
    return line


def chunk_message_lines(header: str, lines: list[str], max_length: int = 4000) -> list[str]:
    chunks: list[str] = []
    current = header

    for line in lines:
        candidate = f"{current}\n{line}"
        if len(candidate) <= max_length:
            current = candidate
            continue

        if current != header:
            chunks.append(current)
            current = line
        else:
            chunks.append(candidate)
            current = header

    if current == header:
        return chunks

    chunks.append(current)
    return chunks


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    config = get_config()
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
    config = get_config()
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
    config = get_config()
    query = update.callback_query
    if query is None or update.effective_user is None:
        return
    if update.effective_user.id != config.telegram_id:
        return

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    parsed = parse_callback_data(query.data or "")
    if parsed is None:
        await query.edit_message_text(text="This action is no longer available.")
        return

    if isinstance(parsed, BookingCallback):
        if parsed.action == BookingCallbackAction.CANCEL:
            await handle_booking_cancel_callback(update, context, parsed)
            return

        await handle_booking_decision_callback(update, context, parsed)
        return

    await handle_choice_pick_callback(context, update, parsed)


def get_puregym_client(context: ContextTypes.DEFAULT_TYPE) -> PureGymClient | None:
    client = context.bot_data.get("puregym_client")
    if client is None:
        return None
    return client


async def handle_booking_decision_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback: BookingCallback,
) -> None:
    query = update.callback_query
    if query is None:
        return

    with get_db_session() as session:
        booking = get_booking_by_participation_id(session, callback.participation_id)
        if booking is None or booking.status != BookingStatus.PENDING:
            await query.edit_message_text(text="This booking has already been handled.")
            return

        if callback.action == BookingCallbackAction.ACCEPT:
            set_booking_status(session, booking, BookingStatus.CONFIRMED)
            session.commit()
            await query.edit_message_text(text="Booking accepted.")
            return

        client = get_puregym_client(context)
        await cancel_booking_from_callback(session, query, callback.participation_id, client)


async def handle_booking_cancel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback: BookingCallback,
) -> None:
    query = update.callback_query
    if query is None:
        return

    with get_db_session() as session:
        client = get_puregym_client(context)
        await cancel_booking_from_callback(session, query, callback.participation_id, client)


async def cancel_booking_from_callback(
    session, query, participation_id: str, client: PureGymClient | None
) -> None:
    booking = get_booking_by_participation_id(session, participation_id)
    if booking is not None and booking.status not in {BookingStatus.PENDING, BookingStatus.CONFIRMED}:
        await query.edit_message_text(text="This booking can no longer be cancelled.")
        return

    if client is None:
        return

    resp = await client.unbook_participation(participation_id)
    if resp.get("status") == "success":
        if booking is not None:
            set_booking_status(session, booking, BookingStatus.CANCELLED)
            session.commit()
        await query.edit_message_text(text="Booking cancelled.")
        return

    logging.debug("Failed to cancel booking %s: %s", participation_id, resp)
    await query.edit_message_text(text="Failed to cancel!")


async def handle_choice_pick_callback(
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    callback: ChoicePickCallback,
) -> None:
    config = get_config()
    query = update.callback_query
    if query is None:
        return

    with get_db_session() as session:
        choice = get_choice_by_id(session, callback.choice_id)
        if choice is None or choice.status != ChoiceStatus.PENDING:
            await query.edit_message_text(text="This selection has already been handled.")
            return

        options = json.loads(choice.options_json)
        if callback.option_index >= len(options):
            await query.edit_message_text(text="This action is no longer available.")
            return
        selected = options[callback.option_index]

        client = get_puregym_client(context)
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

        follow_up_message = build_selected_choice_confirmation_prompt(
            title=selected["title"],
            class_date=selected["date"],
            start_time=selected["startTime"],
            location=selected["location"],
            participation_id=participation_id,
        )
        await query.edit_message_text(text="Booked your selection. Please accept or reject.")
        await context.bot.send_message(
            chat_id=config.telegram_id,
            text=follow_up_message.text,
            reply_markup=message_markup(follow_up_message),
        )


async def get_live_booked_classes(ctx: HandlerContext) -> list[GymClass]:
    config = get_config()
    return filter_by_booked(
        await ctx.client.get_available_classes(
            class_ids=config.class_preferences.interested_classes,
            center_ids=config.class_preferences.interested_centers,
        )
    )


def build_managed_booking_lookup(
    active_bookings: list[ManagedBooking],
) -> tuple[dict[str, ManagedBooking], dict[str, ManagedBooking]]:
    managed_by_participation = {
        booking.participation_id: booking
        for booking in active_bookings
        if booking.participation_id is not None
    }
    managed_by_booking_id = {booking.booking_id: booking for booking in active_bookings}
    return managed_by_participation, managed_by_booking_id


def get_managed_booking(
    gym_class: GymClass,
    managed_by_participation: dict[str, ManagedBooking],
    managed_by_booking_id: dict[str, ManagedBooking],
) -> ManagedBooking | None:
    managed_booking = None
    if gym_class.participationId is not None:
        managed_booking = managed_by_participation.get(gym_class.participationId)
    if managed_booking is None:
        managed_booking = managed_by_booking_id.get(gym_class.bookingId)
    return managed_booking


def build_actionable_bookings(
    bookings: list[GymClass], active_bookings: list[ManagedBooking]
) -> list[ActionableBooking]:
    managed_by_participation, managed_by_booking_id = build_managed_booking_lookup(active_bookings)
    actionable: list[ActionableBooking] = []

    for gym_class in sorted(bookings, key=lambda booking: (booking.date, booking.startTime)):
        managed_booking = get_managed_booking(
            gym_class,
            managed_by_participation,
            managed_by_booking_id,
        )
        if gym_class.participationId is None:
            continue
        if managed_booking is None or managed_booking.status in {
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
        }:
            actionable.append(ActionableBooking(gym_class=gym_class, managed_booking=managed_booking))

    return actionable


def build_manage_booking_prompt(actionable_booking: ActionableBooking):
    gym_class = actionable_booking.gym_class
    participation_id = gym_class.participationId
    if participation_id is None:
        raise ValueError("Actionable bookings must have a participationId")

    if actionable_booking.managed_booking is None:
        return build_cancel_booking_prompt(
            participation_id,
            text=f"External booking:\n{format_telegram_gym_class(gym_class)}\nCancel it if you no longer want it.",
        )

    if actionable_booking.managed_booking.status == BookingStatus.PENDING:
        return build_keep_booking_prompt(
            participation_id,
            text=(
                f"Pending booking:\n{format_telegram_gym_class(gym_class)}\n"
                "Accept to keep it or reject to cancel it."
            ),
        )

    return build_cancel_booking_prompt(
        participation_id,
        text=f"Confirmed booking:\n{format_telegram_gym_class(gym_class)}\nCancel it if you no longer want it.",
    )


def build_manage_summary(actionable_bookings: list[ActionableBooking]) -> str:
    pending_count = sum(
        1
        for item in actionable_bookings
        if item.managed_booking is not None and item.managed_booking.status == BookingStatus.PENDING
    )
    cancellable_count = len(actionable_bookings) - pending_count

    parts: list[str] = []
    if pending_count == 1:
        parts.append("1 pending booking to review")
    elif pending_count > 1:
        parts.append(f"{pending_count} pending bookings to review")

    if cancellable_count == 1:
        parts.append("1 booking you can cancel")
    elif cancellable_count > 1:
        parts.append(f"{cancellable_count} bookings you can cancel")

    return ", ".join(parts).capitalize() + "."


async def booked_classes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    bookings = await get_live_booked_classes(ctx)
    active_bookings = get_active_bookings(ctx.session)

    bookings_by_booking_id = {booking.bookingId: booking for booking in bookings}
    managed_by_participation, managed_by_booking_id = build_managed_booking_lookup(active_bookings)

    live_bookings = sorted(
        bookings_by_booking_id.values(), key=lambda booking: (booking.date, booking.startTime)
    )
    lines: list[str] = []
    for gym_class in live_bookings:
        managed_booking = get_managed_booking(
            gym_class,
            managed_by_participation,
            managed_by_booking_id,
        )

        state = booking_state_label(managed_booking)
        lines.append(format_booking_line(gym_class, state))

    if len(live_bookings) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="You have no upcoming bookings."
        )
        return

    for chunk in chunk_message_lines("Your upcoming bookings:", lines):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)


async def manage_bookings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: HandlerContext,
):
    if update.effective_chat is None:
        return

    bookings = await get_live_booked_classes(ctx)
    active_bookings = get_active_bookings(ctx.session)
    actionable_bookings = build_actionable_bookings(bookings, active_bookings)

    if not actionable_bookings:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Nothing to manage right now.",
        )
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=build_manage_summary(actionable_bookings),
    )
    for actionable_booking in actionable_bookings:
        prompt = build_manage_booking_prompt(actionable_booking)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=prompt.text,
            reply_markup=message_markup(prompt),
        )


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
