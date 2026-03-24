from sqlmodel import Session, col, select

from puregym_bot.datetime_utils import combine_copenhagen
from puregym_bot.storage.models import (
    BookingChoice,
    BookingStatus,
    BotState,
    ChoiceStatus,
    ManagedBooking,
)


def get_bot_state(session: Session) -> BotState:
    bot_state = session.get(BotState, 1)
    if bot_state is None:
        bot_state = BotState(id=1)
        session.add(bot_state)
        session.commit()
        session.refresh(bot_state)
    return bot_state


def set_bot_active(session: Session, is_active: bool) -> BotState:
    bot_state = get_bot_state(session)
    bot_state.is_active = is_active
    session.add(bot_state)
    return bot_state


def get_booking_by_participation_id(session: Session, participation_id: str) -> ManagedBooking | None:
    statement = select(ManagedBooking).where(ManagedBooking.participation_id == participation_id)
    return session.exec(statement).first()


def get_booking_by_booking_id(session: Session, booking_id: str) -> ManagedBooking | None:
    statement = select(ManagedBooking).where(ManagedBooking.booking_id == booking_id)
    return session.exec(statement).first()


def get_active_bookings(session: Session) -> list[ManagedBooking]:
    statement = select(ManagedBooking).where(
        col(ManagedBooking.status).in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
    )
    return list(session.exec(statement).all())


def get_pending_bookings(session: Session) -> list[ManagedBooking]:
    statement = select(ManagedBooking).where(
        ManagedBooking.status == BookingStatus.PENDING,
    )
    return list(session.exec(statement).all())


def get_handled_bookings_for_slot(
    session: Session,
    slot_date: str,
    slot_start: str,
    slot_end: str,
) -> list[ManagedBooking]:
    slot_start_dt = combine_copenhagen(slot_date, slot_start)
    slot_end_dt = combine_copenhagen(slot_date, slot_end)
    statement = select(ManagedBooking).where(
        ManagedBooking.class_datetime >= slot_start_dt,
        ManagedBooking.class_datetime < slot_end_dt,
        col(ManagedBooking.status).in_(
            [
                BookingStatus.PENDING.value,
                BookingStatus.CONFIRMED.value,
                BookingStatus.CANCELLED.value,
            ]
        ),
    )
    return list(session.exec(statement).all())


def add_managed_booking(session: Session, booking: ManagedBooking) -> None:
    session.add(booking)


def set_booking_status(session: Session, booking: ManagedBooking, status: BookingStatus) -> None:
    booking.status = status
    session.add(booking)


def set_reminder_sent(session: Session, booking: ManagedBooking) -> None:
    booking.reminder_sent = True
    session.add(booking)


def set_message_id(session: Session, booking: ManagedBooking, message_id: int) -> None:
    booking.telegram_message_id = message_id
    session.add(booking)


def get_pending_choice(
    session: Session, slot_date: str, slot_start: str, slot_end: str
) -> BookingChoice | None:
    statement = select(BookingChoice).where(
        BookingChoice.slot_date == slot_date,
        BookingChoice.slot_start == slot_start,
        BookingChoice.slot_end == slot_end,
        BookingChoice.status == ChoiceStatus.PENDING,
    )
    return session.exec(statement).first()


def add_booking_choice(session: Session, choice: BookingChoice) -> None:
    session.add(choice)


def set_choice_status(session: Session, choice: BookingChoice, status: ChoiceStatus) -> None:
    choice.status = status
    session.add(choice)


def set_choice_message_id(session: Session, choice: BookingChoice, message_id: int) -> None:
    choice.message_id = message_id
    session.add(choice)


def get_choice_by_id(session: Session, choice_id: int) -> BookingChoice | None:
    statement = select(BookingChoice).where(BookingChoice.id == choice_id)
    return session.exec(statement).first()
