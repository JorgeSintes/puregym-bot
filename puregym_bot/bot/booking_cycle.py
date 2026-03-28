import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from pydantic import BaseModel
from puregym_mcp.puregym.client import PureGymClient
from puregym_mcp.puregym.filters import filter_by_booked, filter_by_time_slots
from puregym_mcp.puregym.models import GymClass
from telegram.ext import ContextTypes

from puregym_bot.bot.prompts import (
    ButtonSpec,
    MessageSpec,
    build_choice_pick_button,
    build_confirmed_reminder_prompt,
    build_keep_booking_prompt,
    message_markup,
)
from puregym_bot.config import TimeSlot, get_config
from puregym_bot.datetime_utils import combine_copenhagen, copenhagen_now
from puregym_bot.formatting import (
    format_telegram_booking,
    format_telegram_class_summary,
    format_telegram_time,
)
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import BookingChoice, BookingStatus, ManagedBooking
from puregym_bot.storage.repository import (
    add_booking_choice,
    add_managed_booking,
    get_active_bookings,
    get_booking_by_participation_id,
    get_bot_state,
    get_handled_bookings_for_slot,
    get_pending_bookings,
    get_pending_choice,
    set_booking_status,
    set_choice_message_id,
    set_message_id,
    set_reminder_sent,
)


@dataclass(frozen=True)
class SlotOccurrence:
    date: str
    slot_start: str
    slot_end: str


@dataclass
class OutboundPrompt:
    message: MessageSpec
    booking: ManagedBooking | None = None
    choice: BookingChoice | None = None


@dataclass
class StepResult:
    prompts: list[OutboundPrompt] = field(default_factory=list)


class BookingChoiceOption(BaseModel):
    """Typed model for a booking choice option stored in BookingChoice.options_json."""

    booking_id: str
    activity_id: int
    payment_type: str
    title: str
    date: str
    start_time: str
    location: str


def class_datetime(gym_class: GymClass) -> datetime:
    return combine_copenhagen(gym_class.date, gym_class.start_time)


def reminder_text(booking: ManagedBooking, intro: str, outro: str) -> str:
    summary = format_telegram_booking(
        class_datetime=booking.class_datetime,
        title=booking.class_title,
        location=booking.class_location,
        include_cancel_deadline=False,
    )
    return f"{intro}\n{summary}\n{outro}"


def get_matching_slot_occurrence(gym_class: GymClass, time_slots: list[TimeSlot]) -> SlotOccurrence | None:
    class_date = datetime.fromisoformat(gym_class.date).date()
    weekday = class_date.weekday()
    class_start = time.fromisoformat(gym_class.start_time)
    class_end = time.fromisoformat(gym_class.end_time)

    for slot in time_slots:
        if slot.day_of_week != weekday:
            continue
        if slot.start_time <= class_start <= class_end <= slot.end_time:
            return SlotOccurrence(
                date=gym_class.date,
                slot_start=slot.start_time.isoformat(),
                slot_end=slot.end_time.isoformat(),
            )
    return None


def group_by_slot(
    classes: list[GymClass], time_slots: list[TimeSlot]
) -> dict[SlotOccurrence, list[GymClass]]:
    grouped: dict[SlotOccurrence, list[GymClass]] = {}

    for gym_class in classes:
        slot_occurrence = get_matching_slot_occurrence(gym_class, time_slots)
        if slot_occurrence is None:
            continue
        grouped.setdefault(slot_occurrence, []).append(gym_class)
    return grouped


def is_cycle_active(session) -> bool:
    bot_state = get_bot_state(session)
    return bot_state.is_active


async def fetch_candidate_classes(client: PureGymClient, now: datetime) -> list[GymClass]:
    config = get_config()
    from_date = now.strftime("%Y-%m-%d")
    to_date = (now + timedelta(days=config.max_days_in_advance)).strftime("%Y-%m-%d")
    classes = await client.get_available_classes(
        class_ids=config.class_preferences.interested_classes,
        center_ids=config.class_preferences.interested_centers,
        from_date=from_date,
        to_date=to_date,
    )
    classes = filter_by_time_slots(classes, config.class_preferences.available_time_slots)
    classes.sort(key=class_datetime)
    return classes


def reconcile_bookings_missing_in_puregym(
    session,
    booked_by_participation: dict[str, GymClass],
    now: datetime,
) -> StepResult:
    result = StepResult()
    active_bookings = get_active_bookings(session)

    for booking in active_bookings:
        if booking.participation_id in booked_by_participation:
            continue

        if booking.class_datetime <= now:
            if booking.status == BookingStatus.CONFIRMED:
                set_booking_status(session, booking, BookingStatus.ATTENDED)
            else:
                set_booking_status(session, booking, BookingStatus.EXPIRED)
            result.prompts.append(
                OutboundPrompt(
                    message=MessageSpec(text="A booking has passed and is now archived."),
                )
            )
        else:
            set_booking_status(session, booking, BookingStatus.CANCELLED)
            result.prompts.append(
                OutboundPrompt(
                    message=MessageSpec(text="A booking was missing in PureGym and has been cancelled."),
                )
            )

    if result.prompts:
        session.commit()
    return result


def import_untracked_bookings(
    session,
    booked_by_participation: dict[str, GymClass],
) -> StepResult:
    result = StepResult()

    for participation_id, gym_class in booked_by_participation.items():
        existing = get_booking_by_participation_id(session, participation_id)
        if existing is not None:
            continue

        booking = ManagedBooking(
            booking_id=gym_class.booking_id,
            activity_id=gym_class.activity_id,
            payment_type=gym_class.payment_type,
            participation_id=participation_id,
            class_title=gym_class.title,
            class_location=gym_class.location,
            class_datetime=class_datetime(gym_class),
            status=BookingStatus.PENDING,
        )
        add_managed_booking(session, booking)
        session.commit()

        text = (
            "Found a booking not tracked by the bot:\n"
            f"- {format_telegram_class_summary(gym_class.date, gym_class.start_time, gym_class.title, gym_class.location)}\n"
            "Do you want to keep it?"
        )
        result.prompts.append(
            OutboundPrompt(
                booking=booking,
                message=build_keep_booking_prompt(participation_id, text),
            )
        )

    return result


def detect_booking_state_mismatch(
    session,
    booked_by_participation: dict[str, GymClass],
) -> StepResult:
    db_participation_ids = {
        booking.participation_id
        for booking in get_active_bookings(session)
        if booking.participation_id is not None
    }
    puregym_participation_ids = set(booked_by_participation)

    if db_participation_ids == puregym_participation_ids:
        return StepResult()

    db_only = sorted(db_participation_ids - puregym_participation_ids)
    puregym_only = sorted(puregym_participation_ids - db_participation_ids)
    message = (
        "Booking state mismatch detected after reconciliation. "
        f"DB active bookings: {len(db_participation_ids)}, "
        f"PureGym booked classes: {len(puregym_participation_ids)}."
    )
    if db_only:
        message += f" DB-only participation IDs: {', '.join(db_only)}."
    if puregym_only:
        message += f" PureGym-only participation IDs: {', '.join(puregym_only)}."

    logging.warning(message)
    return StepResult(prompts=[OutboundPrompt(message=MessageSpec(text=message))])


def slot_is_blocked(session, slot_occurrence: SlotOccurrence) -> bool:
    pending_choice = get_pending_choice(
        session,
        slot_occurrence.date,
        slot_occurrence.slot_start,
        slot_occurrence.slot_end,
    )
    if pending_choice is not None:
        return True

    handled_bookings = get_handled_bookings_for_slot(
        session,
        slot_occurrence.date,
        slot_occurrence.slot_start,
        slot_occurrence.slot_end,
    )
    return bool(handled_bookings)


def assert_not_booked_in_slot_by_this_point(
    slot_occurrence: SlotOccurrence,
    slot_classes: list[GymClass],
) -> bool:
    booked_in_slot = [gym_class for gym_class in slot_classes if gym_class.participation_id is not None]
    if not booked_in_slot:
        return True

    booking_ids = ", ".join(sorted(gym_class.booking_id for gym_class in booked_in_slot))
    logging.warning(
        "Skipping slot %s %s-%s because booked classes were found without a blocking DB record: %s",
        slot_occurrence.date,
        slot_occurrence.slot_start,
        slot_occurrence.slot_end,
        booking_ids,
    )
    return False


async def handle_slot_booking_actions(
    session,
    client: PureGymClient,
    grouped_by_slot: dict[SlotOccurrence, list[GymClass]],
    active_count: int,
) -> StepResult:
    config = get_config()
    result = StepResult()

    for slot_occurrence in sorted(
        grouped_by_slot.keys(),
        key=lambda item: (item.date, item.slot_start, item.slot_end),
    ):
        if active_count >= config.max_bookings:
            logging.info("Max bookings reached, skipping further booking attempts")
            break

        if slot_is_blocked(session, slot_occurrence):
            continue

        slot_classes = grouped_by_slot[slot_occurrence]
        if not assert_not_booked_in_slot_by_this_point(slot_occurrence, slot_classes):
            continue

        available = [gym_class for gym_class in slot_classes if gym_class.participation_id is None]
        if not available:
            continue

        if len(available) == 1:
            gym_class = available[0]
            logging.info("Attempting to book class %s", gym_class.booking_id)
            response = await client.book_by_ids(
                gym_class.booking_id,
                gym_class.activity_id,
                gym_class.payment_type,
            )
            if response.status != "success":
                logging.info("Booking failed for %s: %s", gym_class.booking_id, response)
                continue

            participation_id = response.participation_id
            if not participation_id:
                logging.info(
                    "Booking response missing participation_id for %s: %s",
                    gym_class.booking_id,
                    response,
                )
                continue

            booking = ManagedBooking(
                booking_id=gym_class.booking_id,
                activity_id=gym_class.activity_id,
                payment_type=gym_class.payment_type,
                participation_id=participation_id,
                class_title=gym_class.title,
                class_location=gym_class.location,
                class_datetime=class_datetime(gym_class),
                status=BookingStatus.PENDING,
            )
            add_managed_booking(session, booking)
            session.commit()
            active_count += 1

            message = build_keep_booking_prompt(
                participation_id,
                text=(
                    "Booked: "
                    f"{
                        format_telegram_booking(
                            class_date=gym_class.date,
                            start_time=gym_class.start_time,
                            title=gym_class.title,
                            location=gym_class.location,
                            waitlist_position=gym_class.waitlist_position,
                        )
                    }\n"
                    "Do you want to keep it?"
                ),
            )
            result.prompts.append(OutboundPrompt(booking=booking, message=message))
            continue

        options: list[BookingChoiceOption] = []
        for gym_class in sorted(available, key=class_datetime):
            options.append(
                BookingChoiceOption(
                    booking_id=gym_class.booking_id,
                    activity_id=gym_class.activity_id,
                    payment_type=gym_class.payment_type,
                    title=gym_class.title,
                    date=gym_class.date,
                    start_time=gym_class.start_time,
                    location=gym_class.location,
                )
            )

        choice = BookingChoice(
            slot_date=slot_occurrence.date,
            slot_start=slot_occurrence.slot_start,
            slot_end=slot_occurrence.slot_end,
            options_json=json.dumps([opt.model_dump() for opt in options]),
        )
        add_booking_choice(session, choice)
        session.commit()
        if choice.id is None:
            raise ValueError("Booking choice ID must be set after commit")
        choice_id = choice.id

        lines = ["Multiple classes match this time slot. Pick one to book:"]
        for idx, option in enumerate(options, start=1):
            lines.append(
                f"{idx}. "
                f"{format_telegram_class_summary(option.date, option.start_time, option.title, option.location)}"
            )

        buttons: tuple[tuple[ButtonSpec, ...], ...] = tuple(
            (
                build_choice_pick_button(
                    choice_id=choice_id,
                    option_index=idx,
                    label=f"{idx + 1}. {format_telegram_time(option.start_time)} {option.title}",
                ),
            )
            for idx, option in enumerate(options)
        )
        result.prompts.append(
            OutboundPrompt(
                choice=choice,
                message=MessageSpec(text="\n".join(lines), buttons=buttons),
            )
        )

    return result


def send_due_reminders(session, now: datetime, reminder_hours: int) -> StepResult:
    result = StepResult()
    threshold = timedelta(hours=reminder_hours)
    active_bookings = get_active_bookings(session)

    for booking in active_bookings:
        if booking.reminder_sent:
            continue

        time_to_class = booking.class_datetime - now
        if time_to_class > threshold:
            continue

        if booking.status == BookingStatus.PENDING and booking.participation_id is not None:
            result.prompts.append(
                OutboundPrompt(
                    booking=booking,
                    message=build_keep_booking_prompt(
                        booking.participation_id,
                        text=reminder_text(
                            booking,
                            intro="Reminder: you have a pending booking coming up.",
                            outro="Do you want to keep it?",
                        ),
                    ),
                )
            )
            set_reminder_sent(session, booking)
            continue

        if booking.status == BookingStatus.CONFIRMED and booking.participation_id is not None:
            result.prompts.append(
                OutboundPrompt(
                    booking=booking,
                    message=build_confirmed_reminder_prompt(
                        booking.participation_id,
                        text=reminder_text(
                            booking,
                            intro="Reminder: your class is coming up soon.",
                            outro="If you changed your mind, cancel now.",
                        ),
                    ),
                )
            )
            set_reminder_sent(session, booking)

    if result.prompts:
        session.commit()
    return result


async def auto_cancel_stale_pending_bookings(
    session,
    client: PureGymClient,
    now: datetime,
    auto_cancel_hours: int,
) -> StepResult:
    result = StepResult()
    threshold = timedelta(hours=auto_cancel_hours)
    pending = get_pending_bookings(session)

    for booking in pending:
        time_to_class = booking.class_datetime - now
        if time_to_class > threshold:
            continue

        if booking.participation_id is None:
            continue

        response = await client.unbook_participation(booking.participation_id)
        if response.status != "success":
            logging.info("Failed to auto-cancel booking %s: %s", booking.booking_id, response)
            continue

        set_booking_status(session, booking, BookingStatus.CANCELLED)
        result.prompts.append(
            OutboundPrompt(
                message=MessageSpec(
                    text=(f"Pending booking was cancelled {auto_cancel_hours}h before class time.")
                ),
            )
        )

    if result.prompts:
        session.commit()
    return result


async def publish_prompts(context: ContextTypes.DEFAULT_TYPE, session, prompts: list[OutboundPrompt]) -> None:
    config = get_config()
    for prompt in prompts:
        sent_message = await context.bot.send_message(
            chat_id=config.telegram_id,
            text=prompt.message.text,
            reply_markup=message_markup(prompt.message),
        )

        if prompt.booking is not None:
            set_message_id(session, prompt.booking, sent_message.message_id)
            session.commit()

        if prompt.choice is not None:
            set_choice_message_id(session, prompt.choice, sent_message.message_id)
            session.commit()


async def run_booking_cycle(context: ContextTypes.DEFAULT_TYPE) -> None:
    config = get_config()
    now = copenhagen_now()
    client = context.bot_data.get("puregym_client")
    if client is None:
        raise ValueError("No PureGym client found")

    with get_db_session() as session:
        if not is_cycle_active(session):
            logging.info("Booking cycle skipped because bot is inactive")
            return

    logging.info("Running booking cycle: {%s}", now.isoformat())
    classes = await fetch_candidate_classes(client, now)
    booked_classes = filter_by_booked(classes)
    booked_by_participation = {
        item.participation_id: item for item in booked_classes if item.participation_id
    }
    grouped = group_by_slot(classes, config.class_preferences.available_time_slots)

    with get_db_session() as session:
        result = reconcile_bookings_missing_in_puregym(session, booked_by_participation, now)
        await publish_prompts(context, session, result.prompts)

        result = import_untracked_bookings(session, booked_by_participation)
        await publish_prompts(context, session, result.prompts)

        result = detect_booking_state_mismatch(session, booked_by_participation)
        await publish_prompts(context, session, result.prompts)

        active_count = len(get_active_bookings(session))
        result = await handle_slot_booking_actions(session, client, grouped, active_count)
        await publish_prompts(context, session, result.prompts)

        result = send_due_reminders(session, now, config.booking_reminder_hours)
        await publish_prompts(context, session, result.prompts)

        result = await auto_cancel_stale_pending_bookings(
            session,
            client,
            now,
            config.pending_auto_cancel_hours,
        )
        await publish_prompts(context, session, result.prompts)
